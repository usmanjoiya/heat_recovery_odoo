# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import json
import logging
from collections import defaultdict

import pycountry

from odoo import fields, models, _
from odoo.exceptions import ValidationError

from .utils import IntuitResponse


_logger = logging.getLogger(__name__)

TRACK_FIELDS_CONTACT = [
    'name', 'parent_id', 'phone', 'mobile', 'email',
    'country_id', 'city', 'state_id', 'street', 'street2', 'zip',
]


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'qbo.transaction.mixin']

    _qbo_map = 'qbo.map.partner'

    name = fields.Char(tracking=True)
    parent_id = fields.Many2one(tracking=True)
    phone = fields.Char(tracking=True)
    mobile = fields.Char(tracking=True)
    email = fields.Char(tracking=True)
    country_id = fields.Many2one(tracking=True)
    city = fields.Char(tracking=True)
    state_id = fields.Many2one(tracking=True)
    street = fields.Char(tracking=True)
    street2 = fields.Char(tracking=True)
    zip = fields.Char(tracking=True)

    qbo_partner_ids = fields.One2many(
        comodel_name=_qbo_map,
        inverse_name='partner_id',
        string='QBO Partner',
        readonly=False,
    )

    def export_partner_to_qbo(self):
        """Export Partners to the Intuit company. Call from UI."""
        _logger.info('Export Partners "%s" to QBO.' % self.ids)
        requested_types = self.env.context.get('qbo_partner_type')
        skip_wizard = self.env.context.get('skip_qbo_partner_wizard')
        if not (requested_types and skip_wizard):
            name = _('QBO Partner Options')
            view = self.env.ref('quickbooks_sync_online.qbo_help_wizard_form_view')
            ctx = {'active_ids': self.env.context.get('active_ids')}
            return self.env['qbo.help.wizard'].run_wizard(name, view.id, ctx)

        company = self.define_transaction_company()
        company._check_qbo_auth()

        export_dict, __ = self.with_context(raise_exception=True)\
            ._collect_qbo_export_dict(requested_types.split(','), company)

        return company._process_qbo_export_dict(export_dict)

    def update_partner_in_qbo(self):
        """Update Partner to the Intuit company."""
        _logger.info('Update partners "%s" to Intuit.' % self.ids)
        company = self.define_transaction_company()
        company._check_qbo_auth()

        records = self.browse()
        for rec in self:
            if rec.qbo_partner_ids.filtered(lambda r: r.company_id == company):
                records |= rec

        return records._update_records_to_qbo(company)

    def write(self, vals):
        if self.env.context.get('no_check_intuit_update'):
            return super(ResPartner, self).write(vals)

        intuit_update_required = False
        track_fields = self._qbo_track_fields()
        for key in vals.keys():
            if key in track_fields:
                intuit_update_required = True
                break

        if not intuit_update_required:
            return super(ResPartner, self).write(vals)

        for rec in self:
            map_objects_before = rec.qbo_partner_ids
            super(ResPartner, rec).write(vals)
            map_objects_after = rec.qbo_partner_ids

            if map_objects_before and map_objects_before == map_objects_after:
                rec.with_context(no_check_intuit_update=True).write({
                    'qbo_update_required': True,
                })

        return True

    @staticmethod
    def _get_qbo_unique_identifier():
        return 'DisplayName'

    @staticmethod
    def _qbo_track_fields():
        return TRACK_FIELDS_CONTACT

    def _prepare_qbo_name(self, params=None):
        self.ensure_one()
        name = self.name
        if not params:
            return name

        map_type = params.get('map_type')
        if map_type:
            name = f'{name} ({map_type})'

        currency = params.get('ensure_qbo_currency')
        if currency:
            name = f'{name} [{currency}]'

        return name

    def _format_duplicate_name(self):
        return 'partner', self.name, 'Partners'

    def _check_qbo_duplicate(self, *args, **kw):
        kw['alias'] = 'Partner'
        return super(ResPartner, self)._check_qbo_duplicate(*args, **kw)

    def _any_qbo_checking(self, map_type, company):
        self._check_qbo_duplicate(company.id, map_type=map_type)
        return True

    def _update_qbo_search_domain(self, domain, map_type):
        self.ensure_one()
        res = super(ResPartner, self)._update_qbo_search_domain(domain, map_type)
        if map_type:
            complex_name = f'{self.name} ({map_type})'

        currency_name = self.env.context.get('ensure_qbo_currency')
        if currency_name:
            complex_name = f'{complex_name} [{currency_name}]'

        res[0] = ('qbo_name', '=', complex_name)
        res.append(('qbo_lib_type', 'in', self.map_types))
        return res

    def _is_intuit_taxable_customer(self, company_id):
        self.ensure_one()
        map_partner = self._get_qbo_mapping('customer', company_id)
        # Get actual customer-data from Intuit
        result, code = map_partner._refresh_qbo_mapping_body()

        if not IntuitResponse.is_ok(code):
            raise ValidationError(result)

        qbo_object_body = json.loads(map_partner.qbo_object)
        return qbo_object_body.get('Taxable', False)

    def _parse_qbo_address(self):
        code, iso = self.country_id.code, ''
        if code:
            py_country = pycountry.countries.get(alpha_2=code)
            iso = py_country.alpha_3 if py_country else iso
        vals = {
            'City': self.city or '',
            'Country': iso,
            'CountrySubDivisionCode': self.state_id.name or '',
            'Line1': self.street or '',
            'Line2': self.street2 or '',
            'PostalCode': self.zip or '',
        }
        return vals

    def _set_qbo_values(self, qbo_lib_model, company, **kw):
        self.ensure_one()

        kwargs = kw.get('ctx_params') or {}
        map_type = qbo_lib_model.qbo_object_name.lower()
        kwargs['map_type'] = map_type

        currency_ref = getattr(qbo_lib_model, 'CurrencyRef', {}) or {}
        if isinstance(currency_ref, dict):
            currency_name = currency_ref.get('value')
        else:
            currency_name = currency_ref.value

        if currency_name and not company.external_currency_belong_company(currency_name):
            kwargs['ensure_qbo_currency'] = currency_name

        qbo_name = self._prepare_qbo_name(kwargs)
        currency_ref = kwargs.get('ensure_qbo_currency') or currency_name or self.currency_id.name

        qbo_lib_model.Active = self.active
        qbo_lib_model.DisplayName = qbo_name
        qbo_lib_model.GivenName = self.name
        qbo_lib_model.CompanyName = self.parent_id.name or ''
        qbo_lib_model.PrimaryPhone = {'FreeFormNumber': self.phone or ''}
        qbo_lib_model.Mobile = {'FreeFormNumber': self.mobile or ''}
        qbo_lib_model.CurrencyRef = {'value': currency_ref or ''}
        qbo_lib_model.PrimaryEmailAddr = {'Address': self.email or ''}
        qbo_lib_model.BillAddr = self._parse_qbo_address()

    def _collect_qbo_export_dict(self, map_types, company):
        _logger.info('Collect "%s" export dict "%s". Redefined.' % (str(map_types), self.ids))
        allowed_ids_dict = {}
        export_dict = defaultdict(lambda: defaultdict(list))

        for map_type in map_types:
            export_dict_, allowed_ids = super(ResPartner, self)\
                ._collect_qbo_export_dict([map_type], company)

            if export_dict_[self._name][map_type]:
                export_dict[self._name][map_type] = export_dict_[self._name][map_type]
                allowed_ids_dict[map_type] = allowed_ids

        return export_dict, allowed_ids_dict

    def _update_records_to_qbo(self, company):
        """Update Partners to Intuit by Cron."""
        _logger.info('Update partners "%s" to Intuit by Cron.' % self.ids)

        for partner in self.with_context(company_id=company.id):
            mappings = partner.qbo_partner_ids.filtered(lambda r: r.company_id == company)
            partner._write_info('pending', '', company.id)

            for mapping in mappings:
                map_type = mapping.qbo_lib_type
                job_kwargs = partner._get_transaction_job_kwargs(map_type)
                job_kwargs['description'] = (
                    f'Update {partner._description} "{partner.display_name}" ({map_type}) to QBO'
                )
                partner._mark_failed_jobs_as_cancel(identity_key=job_kwargs['identity_key'])

                partner.with_delay(**job_kwargs)._update_one_odoo_to_qbo(mapping)

    def _export_qbo_one(self, map_type, company, ctx_params=None):
        self.ensure_one()
        qbo_lib_model = self._init_qbo_lib_class(map_type)
        self._set_qbo_values(qbo_lib_model, company, ctx_params=ctx_params)
        return self._perform_export_qbo_one(qbo_lib_model, company)

    def _export_qbo_batch(self, map_type, company, ctx_params):
        _logger.info('Export to QBO "%s". Create jobs.' % str(self))

        for rec in self.with_context(company_id=company.id):
            rec._write_info('pending', '', company.id)

            job_kwargs = rec._get_transaction_job_kwargs(map_type)
            rec._mark_failed_jobs_as_cancel(identity_key=job_kwargs['identity_key'])

            rec.with_delay(**job_kwargs)._export_qbo_one(map_type, company, ctx_params)

        return True

    def to_qbo_json(self):
        self.ensure_one()

        company = self.define_transaction_company()

        qbo_lib_model_c = self._init_qbo_lib_class('customer')
        self._set_qbo_values(qbo_lib_model_c, company)

        qbo_lib_model_v = self._init_qbo_lib_class('vendor')
        self._set_qbo_values(qbo_lib_model_v, company)

        return self._display_qbo_json(
            f'DEBUG: {self.name}',
            {
                'CUSTOMER JSON': qbo_lib_model_c.to_dict(),
                'VENDOR JSON': qbo_lib_model_v.to_dict(),
            },
        )

    @staticmethod
    def _essential_ctx_variables():
        return [
            'ensure_qbo_currency',
        ]

    def _ensure_qbo_currency(self, invoice):
        currency_name = invoice.currency_id.name
        if not invoice.company_id.external_currency_belong_company(currency_name):
            return self.with_context(ensure_qbo_currency=currency_name)
        return self

    def _extract_essential_context(self):
        result = list()
        for key in self._essential_ctx_variables():
            value = self._context.get(key)
            if value:
                result.append((key, value))
        return tuple(result)
