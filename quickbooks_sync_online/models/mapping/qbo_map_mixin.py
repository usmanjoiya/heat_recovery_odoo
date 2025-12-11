# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import json
import logging
from copy import deepcopy
from collections import defaultdict

from odoo import models, fields, _
from odoo.exceptions import ValidationError

from ..utils import catch_exception, IntuitResponse, RouteParser, TaxSuiter

_logger = logging.getLogger(__name__)

try:
    from quickbooks.batch import batch_create
except (ImportError, IOError) as ex:
    _logger.error(ex)


MAX_RESULTS = 100
SUMMARY = {
    'mapped': _('- %s records were mapped:\n'),
    'skipped': _('- %s records already had map objects and were skipped:\n'),
    'duplicated': _('- %s records have multiple duplicates. Make manual mapping for:\n'),
    'created': _('- %s records were created.\n'),
    'to_create': _(
        '- %s records have to be created manually, afterwards they might be mapped:\n'
    ),
}


class QboMapMixin(models.AbstractModel):
    _name = 'qbo.map.mixin'
    _description = 'Abstract proxy QBO model'
    _rec_name = 'qbo_name'
    _order = 'id desc'

    _res_model = ''
    _qbo_lib_class = None
    _related_field = ''
    _odoo_routes = {}
    _map_routes = {}

    qbo_id = fields.Char(
        string='QBO ID',
        required=True,
        readonly=True,
    )
    qbo_name = fields.Char(
        string='QBO Name',
        required=True,
        readonly=True,
    )
    qbo_object = fields.Text(
        string='JSON Body',
    )
    is_imported = fields.Boolean(
        string='Is Imported',
        readonly=True,
    )
    is_exported = fields.Boolean(
        string='Is Exported',
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )
    qbo_lib_type = fields.Selection(
        selection=[
            ('item', 'Product'),
            ('customer', 'Customer'),
            ('vendor', 'Vendor'),
            ('invoice', 'CustomerInvoice'),
            ('creditmemo', 'CustomerCredit'),
            ('bill', 'VendorBill'),
            ('vendorcredit', 'VendorRefund'),
            ('account', 'Account'),
            ('taxrate', 'Tax'),
            ('taxcode', 'TaxCode'),
            ('term', 'PaymentTerm'),
            ('payment', 'Payment'),
            ('billpayment', 'BillPayment'),
            ('paymentmethod', 'PaymentMethod'),
            ('salesreceipt', 'SalesReceipt'),
            ('department', 'Department'),
        ],
        string='QBO Lib Type',
        readonly=True,
    )

    @property
    def qbo_lib_class(self):
        self.ensure_one()
        return self._qbo_lib_class[self.qbo_lib_type]

    def write(self, vals):
        res = False
        for rec in self:
            rel_id_before = rec.odoo_record

            res = super(QboMapMixin, rec).write(vals)

            rel_id_after = rec.odoo_record
            if not rel_id_before and rel_id_after and hasattr(rel_id_after, 'qbo_state'):
                rel_id_after._write_info('proxy', '', rec.company_id.id)
            elif not rel_id_after and rel_id_before and hasattr(rel_id_before, 'qbo_state'):
                rel_id_before._write_info('todo', '', rec.company_id.id)

        return res

    def get_odoo_routes(self):
        return self._odoo_routes

    def get_map_routes(self):
        return self._map_routes

    def define_transaction_company(self):
        ctx_id = int(self.env.context.get('apply_company', 0))
        return self.env['res.company'].browse(ctx_id) if ctx_id else self.env.company

    def qbo_map_list(self):
        """Get list of the types of the linked Intuit lib classes."""
        return self._qbo_lib_class.qbo_types()

    @property
    def odoo_model(self):
        """Get linked Odoo model to current one."""
        self = self.browse()
        if hasattr(self, self._related_field):
            return self.env[self._res_model]
        return None

    @property
    def odoo_record(self):
        """Get related Odoo instance to current one."""
        if hasattr(self, self._related_field):
            return getattr(self, self._related_field)
        return None

    def create_instance_in_odoo(self):
        """Create Odoo object from QBO-map object."""
        for rec in self:
            odoo_object = rec.odoo_record
            if odoo_object or odoo_object is None:
                return odoo_object or None

            if not self.get_odoo_routes():
                return None

            return rec._create_odoo_instance()

    def get_data_from_qbo(self):
        """Import all objects from Intuit company by the serial multiple requests."""
        company = self.define_transaction_company()
        company._check_qbo_auth()

        for map_type in self.qbo_map_list():
            job_kwargs = dict(
                description=f'Import "{self._description}" from QBO',
            )
            self.with_context(company_id=company.id)\
                .with_delay(**job_kwargs)._get_data_from_qbo(company, map_type)

    def get_all_data_from_qbo(self):
        """Import all objects from Intuit company in a single request."""
        company = self.define_transaction_company()
        company._check_qbo_auth()

        for map_type in self.qbo_map_list():
            job_kwargs = dict(
                description=f'Import "{self._description}" from QBO (single request)',
            )
            self.with_context(company_id=company.id)\
                .with_delay(**job_kwargs)._get_all_data_from_qbo(company, map_type)

    def try_to_map(self, do_create=True, summary=True):
        summary_dict = defaultdict(set)
        to_create_set = set()

        for rec in self:
            rec_info = (rec.qbo_id, rec.qbo_name)
            if rec.odoo_record:
                summary_dict['skipped'].add(rec_info)
                continue

            for domain in rec._update_odoo_search_domain([('name', '=', rec.qbo_name)]):
                eq_object = rec._advance_search(domain)

                if len(eq_object) == 1:
                    mapping = eq_object._get_qbo_mapping(
                        rec.qbo_lib_type,
                        rec.company_id.id,
                    )
                    if mapping:
                        summary_dict['skipped'].add(rec_info)
                    else:
                        setattr(rec, rec._related_field, eq_object.id)
                        summary_dict['mapped'].add(rec_info)

                    to_create_set.discard(rec.id)
                    summary_dict['created'].discard(rec_info)
                    break

                if len(eq_object) > 1:
                    summary_dict['duplicated'].add(rec_info)
                    break

                if do_create:
                    to_create_set.add(rec.id)
                    summary_dict['created'].add(rec_info)
                else:
                    summary_dict['to_create'].add(rec_info)

        for rec_id in to_create_set:
            odoo_instance = self.browse(rec_id)._create_odoo_instance()

            if not odoo_instance:
                map_record = self.filtered(lambda r: r.id == rec_id)
                rec_info = (map_record.qbo_id, map_record.qbo_name)
                summary_dict['created'].discard(rec_info)

        if not summary:
            return True

        ordered_dict = self._order_summary_dict(summary_dict)

        wizard = self.env['qbo.help.wizard'].create({
            'information': self._format_summary_map_info(ordered_dict),
        })
        view = self.env.ref('quickbooks_sync_online.qbo_help_wizard_info_form_view')
        return wizard.run_wizard(_('Mapping Information'), view.id, {})

    @catch_exception
    def _fetch_qbo_all(self, company, map_type):
        """Fetch all objects from Intuit company in a single request."""
        return self._qbo_lib_class[map_type].all(qb=company.get_quickbooks_api_client())

    @catch_exception
    def _fetch_qbo_batch(self, company, map_type, position):
        """Fetch a batch of objects from Intuit company."""
        params = {
            'start_position': position,
            'max_results': MAX_RESULTS,
            'order_by': 'Id',
            'qb': company.get_quickbooks_api_client(),
        }
        return self._qbo_lib_class[map_type].filter(**params)

    @catch_exception
    def _fetch_qbo_one_by_id(self, company, map_type, qbo_id):
        """Fetch a single object from Intuit company by ID."""
        return self._qbo_lib_class[map_type].get(qbo_id, qb=company.get_quickbooks_api_client())

    @catch_exception
    def _fetch_qbo_one_by_name(self, company, map_type, name_dict):
        """
        Fetch a single object from Intuit by unique name.

        Example:: name_dict = {'Name': 'Guido van Rossum'}
        """
        return self._qbo_lib_class[map_type].filter(qb=company.get_quickbooks_api_client(), **name_dict)

    @catch_exception
    def _fetch_qbo_by_query(self, company, map_type, condition):
        """Fetch a batch of objects from Intuit company by row query."""
        qbo_lib_class = self._qbo_lib_class[map_type]
        row_query = "SELECT * FROM %s WHERE %s" % (qbo_lib_class.qbo_object_name, condition)
        return qbo_lib_class.query(row_query, qb=company.get_quickbooks_api_client())

    @catch_exception
    def _save_qbo_one(self, company, qbo_lib_model):
        """Save an object to Intuit company."""
        return qbo_lib_model.save(qb=company.get_quickbooks_api_client())

    @catch_exception
    def _save_qbo_batch(self, company, qbo_model_list):
        """Save a batch of objects to Intuit company in a single request."""
        return batch_create(qbo_model_list, qb=company.get_quickbooks_api_client())

    @catch_exception
    def _delete_qbo_by_id(self, company):
        """Delete an object from intuit Company by Id."""
        record = self.instance_from_json()
        return record.delete(qb=company.get_quickbooks_api_client())

    def instance_from_json(self):
        return self.qbo_lib_class.from_json(json.loads(self.qbo_object))

    def instance_from_external(self):
        instance, __ = self.fetch_qbo_one()
        return instance

    def fetch_qbo_one(self):
        self.ensure_one()
        result, code = self._fetch_qbo_one_by_id(self.company_id, self.qbo_lib_type, self.qbo_id)
        return result, code

    def _update_odoo_search_domain(self, domain):
        """
        Hook method for defining right domain in during 'Map by Name' method.
        Returns list of domains for several attempts to match current record.
        """
        return [domain]

    def _prepare_map_name(self):
        return self.qbo_name

    def _get_existing_ids(self, company_id, map_type, add_condition=None):
        domain = [
            ('qbo_lib_type', '=', map_type),
            ('company_id', '=', company_id),
        ]
        add_condition and domain.extend(add_condition)
        record_list = self.search_read(
            domain=domain,
            fields=['qbo_id'],
        )
        return [rec.get('qbo_id') for rec in record_list]

    def _parse_values_from_lib_obj(self, qbo_lib_model):
        dirty_vals = self._parse_routes(qbo_lib_model.to_dict(), self.get_map_routes())
        return self._remove_dots(dirty_vals)

    def _parse_map_tax_ids(self, qbo_lib_model, company_id):
        """Parse QBO taxes from `qbo_lib_object`. Mainly for `sale.order` and `account.move`.'"""
        tax_qbo_ids = []

        if not qbo_lib_model.TxnTaxDetail:
            return tax_qbo_ids

        for rec in qbo_lib_model.TxnTaxDetail.TaxLine:
            # TODO: Currently we are handling only `percent based` taxes
            tax_value = rec.TaxLineDetail.TaxRateRef.value
            if rec.Amount and rec.TaxLineDetail.PercentBased:
                tax_qbo_ids.append(tax_value)
            else:
                _logger.warning(
                    'QuickBooks: non percent-based external tax "%s" was skipped (%s, QboID=%s)',
                    tax_value,
                    self._description,
                    qbo_lib_model.Id,
                )

        MapTax = self.env['qbo.map.tax']
        map_ids = MapTax.browse()

        for external_id in tax_qbo_ids:
            map_id = MapTax._get_mapping_from_external(external_id, company_id, True)
            map_ids |= map_id
        return map_ids

    def _prepare_map_lines(self, qbo_lib_model):
        vals_list = list()

        def extract(dict_, attr):
            return dict_.get(attr, {}).get('value', False)

        company_id = self.company_id.id
        MapTax = self.env['qbo.map.tax']
        MapProduct = self.env['qbo.map.product']

        tax_router = TaxSuiter(qbo_lib_model).get_fit_taxes()

        for line in qbo_lib_model.Line:
            line_datail = getattr(line, 'SalesItemLineDetail', False)

            if not line_datail:
                continue

            if not isinstance(line_datail, dict):
                line_datail = line_datail.to_dict()

            # 1. Find product
            external_pr_id = extract(line_datail, 'ItemRef')
            map_product = MapProduct._get_mapping_from_external(external_pr_id, company_id, True)

            assert len(map_product) == 1, _('Expected single mapping.')

            # 2. Find taxes
            qbo_tax_ids = tax_router.get(line.LineNum, [])
            if not qbo_tax_ids:
                map_tax_ids = qbo_tax_ids
            else:
                map_tax = MapTax.browse()
                for external_tax_id in qbo_tax_ids:
                    map_id = MapTax._get_mapping_from_external(external_tax_id, company_id, True)

                    assert len(map_id) == 1, _('Expected single mapping.')

                    map_tax |= map_id

                map_tax_ids = map_tax.ids

            vals_list.append({
                'line_num': line.LineNum,
                'item_map_id': map_product.id,
                'tax_class': extract(line_datail, 'TaxClassificationRef'),
                'tax_code': extract(line_datail, 'TaxCodeRef'),
                'tax_map_ids': [(6, 0, map_tax_ids)],
            })

        return vals_list

    def _get_mapping_from_external(self, external_id, company_id, raise_if_not_found=False):
        mapping_id = self.search([
            ('qbo_id', '=', str(external_id)),
            ('company_id', '=', company_id),
        ])
        if raise_if_not_found and not mapping_id:
            raise ValidationError(_(
                '"%s": mapping not found, QboID=%s, company=%s'
            ) % (self._description, external_id, company_id))
        return mapping_id

    def _remove_dots(self, vals):
        """
        Serializing values after extracting them into the 'temporary ones with the dot'.

        Example:: vals = {'a.b': 1, 'a.c': 2, 'd': 3} --> vals = {'a': {'b': 1, 'c': 2}}, 'd': 3}
        """
        cleaned_vals = {}
        for raw_field, value in vals.items():
            if raw_field.count('.'):
                sub_fields = raw_field.split('.')
                current_dict = cleaned_vals
                for field in sub_fields[:-1]:
                    current_dict.setdefault(field, {})
                    current_dict = current_dict[field]
                current_dict[sub_fields[-1]] = value
            else:
                cleaned_vals[raw_field] = value
        return cleaned_vals

    def _parse_routes(self, dict_to_parse, routes):
        """Extract values from QBO dict-object by routes."""
        parsed_vals = {}
        if not routes:
            return parsed_vals

        for field, (route, def_value) in routes.items():
            with RouteParser(field, route, def_value, dict_to_parse, parsed_vals) as qbo_route:
                qbo_route.parse()
        return parsed_vals

    def _adjust_odoo_values(self, vals):
        """
        It's a hook-method for redefining during creating Odoo instance from map instance.
        Mainly for handling the temporary values after "remove dots".

        Example::
        vals = {'a': {'b': 1, 'c': 2}}, 'd': 3} --> {'a': a['b'] + a['c'], 'd': 3}
        """
        return vals

    def _adjust_map_values(self, vals, qbo_lib_model):
        """
        It's a hook-method for redefining during creating map instance from Intuit response.
        It's important to invoke a 'super' method to set up the 'default qbo name'.
        """
        if not vals.get('qbo_name'):
            vals['qbo_name'] = qbo_lib_model.qbo_object_name.lower()
            vals['qbo_object'] = qbo_lib_model.to_json()

        return vals

    def _post_create_map(self, qbo_lib_model):
        """
        It's a post-hook-method for redefining during creating map instance from Intuit response.
        """
        pass

    @staticmethod
    def _format_summary_map_info(dct):
        info = ''
        for key, values_set in dct.items():
            items = [' ' * 8 + '. '.join(val) for val in values_set]
            info += SUMMARY.get(key, '- %s') % len(values_set) + '\n'.join(items) + '\n\n'
        return info

    @staticmethod
    def _order_summary_dict(def_dict):
        """First sets the 'matched' records and removes the dict keys where the values are empty."""
        ordered_dict = {}
        if 'mapped' in def_dict:
            mapped_ids = deepcopy(def_dict['mapped'])
            ordered_dict['mapped'] = mapped_ids
            del def_dict['mapped']

            for key, items in def_dict.items():
                items -= mapped_ids
                if items:
                    ordered_dict[key] = items
        else:
            ordered_dict = dict(def_dict)
        return ordered_dict

    def _extract_currency_name(self, *args, **kw):
        raise NotImplementedError()

    def _refresh_qbo_mapping_body(self):
        """Refresh QBO object from the Intuit company."""
        self.ensure_one()
        record = self.odoo_record
        result, code = self.fetch_qbo_one()

        if not IntuitResponse.is_ok(code):
            if record:
                record.with_context(apply_company=self.company_id.id)._write_hint(result, code)

            return result, code

        self.write({'qbo_object': result.to_json()})

        if record:
            record._write_info('proxy', '', self.company_id.id)

        return result, code

    def _update_map_one(self, qbo_lib_model):
        """Update mapping in Odoo from Intuit response object."""
        self.ensure_one()
        vals = self._parse_values_from_lib_obj(qbo_lib_model)
        vals_upd = self._adjust_map_values(vals, qbo_lib_model)
        result = self.write(vals_upd)
        _logger.info('Map object "%s" was updated: %s.' % (self._prepare_map_name(), result))
        return result

    def _create_qbo_mapping(self, qbo_lib_model, extra_vals, existing_ids=None):
        """Create mapping in Odoo from Intuit response object."""
        company_id = self.env.context.get('apply_company')
        if not company_id:
            raise ValidationError(_('Company not defined during creating QBO mapping.'))

        qbo_id = qbo_lib_model.Id
        map_type = qbo_lib_model.qbo_object_name.lower()

        ex_ids = existing_ids or self._get_existing_ids(company_id, map_type)

        if ex_ids and (qbo_id in ex_ids):
            _logger.info('QBO mapping with id=%s already exists.', qbo_id)

            mapping = self.search([
                ('qbo_id', '=', qbo_id),
                ('qbo_lib_type', '=', map_type),
                ('company_id', '=', company_id),
            ], limit=1)

            mapping._update_map_one(qbo_lib_model)

            return mapping.browse()

        values = {
            'qbo_id': qbo_id,
            'qbo_lib_type': map_type,
            'company_id': company_id,
            'qbo_object': qbo_lib_model.to_json(),
            **extra_vals,
            **self._parse_values_from_lib_obj(qbo_lib_model),
        }
        values_upd = self._adjust_map_values(values, qbo_lib_model)

        mapping = self.create(values_upd)
        mapping._post_create_map(qbo_lib_model)

        _logger.info('QBO mapping was created: %s.', mapping)

        return mapping

    def _handle_received_records(self, rec_list, map_type, company_id):
        map_ids = self.browse()

        if not rec_list:
            _logger.info('There are no new QBO records for import.')
            return map_ids

        ex_vals = dict(is_imported=True)
        ex_ids = self._get_existing_ids(company_id, map_type)
        self_ = self.with_context(apply_company=company_id)

        for qbo_lib_model in rec_list:
            map_ids |= self_._create_qbo_mapping(qbo_lib_model, ex_vals, existing_ids=ex_ids)

        return map_ids

    def _get_data_from_qbo(self, company, map_type):
        response_list = list()

        while True:
            position = len(response_list) + 1
            result, code = self._fetch_qbo_batch(company, map_type, position)

            if not IntuitResponse.is_ok(code):
                raise ValidationError(result)

            response_list.extend(result)

            if len(result) < MAX_RESULTS:
                _logger.info('All QBO records have been fetched.')
                break

        return self._handle_received_records(response_list, map_type, company.id)

    def _get_all_data_from_qbo(self, company, map_type):
        result, code = self._fetch_qbo_all(company, map_type)

        if not IntuitResponse.is_ok(code):
            raise ValidationError(result)

        return self._handle_received_records(result, map_type, company.id)

    def _create_odoo_instance(self):
        self.ensure_one()
        qbo_object_body = json.loads(self.qbo_object)
        dirty_vals = self._parse_routes(qbo_object_body, self.get_odoo_routes())
        cleaned_vals = self._remove_dots(dirty_vals)
        proven_vals = self._adjust_odoo_values(cleaned_vals)

        if not proven_vals:
            _logger.info(
                'Odoo instance may not be created from mapping "%s".' % self._prepare_map_name()
            )
            return self.odoo_model

        odoo_instance = self.odoo_model.create(proven_vals)
        setattr(self, self._related_field, odoo_instance.id)
        _logger.info(
            'Odoo instance "%s" was created from mapping.' % self._prepare_map_name()
        )
        return odoo_instance

    def _advance_search(self, domain):
        return self.odoo_model.search(domain)

    def _update_qbo_one(self):
        self.ensure_one()
        company = self.company_id
        odoo_record = getattr(self, self._related_field)

        odoo_record._check_requirements(company)
        odoo_record._write_info('pending', '', company.id)

        return odoo_record._update_one_odoo_to_qbo(self)

    def _action_force_update_map_to_qbo(self):
        """
        Developer mode! Action to call force update mapping records to QBO.
        Note that it's only for records with `_related_field` and `is_exported` preperties
        which means it won't be performed on products as categories for example.
        """
        company_ids = self.mapped('company_id').qbo_company_ids
        if not company_ids:
            return False

        self = self.filtered(
            lambda x: x.company_id.id in company_ids.ids
            and getattr(x, x._related_field)
        )

        pattern = self._get_force_update_pattern()

        for rec in self:
            job_kwargs = rec._get_transaction_job_kwargs()
            job_kwargs['description'] = pattern % (rec.qbo_name, rec.qbo_id)

            rec.with_context(company_id=self.company_id.id)\
                .with_delay(**job_kwargs)\
                ._update_qbo_one()

        return True

    @staticmethod
    def _get_force_update_pattern():
        return 'Force update to QBO: %s [%s]'
