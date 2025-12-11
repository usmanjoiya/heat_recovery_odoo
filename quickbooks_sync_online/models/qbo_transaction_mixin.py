# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import json
import logging
from collections import defaultdict

from odoo import models, fields, SUPERUSER_ID, _
from odoo.exceptions import ValidationError

from .utils import IntuitResponse
from .exceptions import OdooJobError

_logger = logging.getLogger(__name__)

try:
    from quickbooks.exceptions import QuickbooksException
except (ImportError, IOError) as ex:
    _logger.error(ex)


MODELS_TO_EXPORT = {  # (name : queue-job priority)
    'res.partner': 11,
    'product.category': 12,
    'product.product': 13,
    'account.move': 14,
    'account.payment': 15,
}

ERROR_MESSAGES = {
    'failed': _(
        'QuickBooks Job Error! '
        'More details on the "QuickBooks Online" tab.'
    ),
    'rejected': _(
        'QuickBooks Job has not been created! '
        'More details on the "QuickBooks Online" tab.'
    ),
}


class QboTransactionMixin(models.AbstractModel):
    _name = 'qbo.transaction.mixin'
    _description = 'Additional logic for data communication with the Intuit'

    _qbo_map = None

    qbo_transaction_info = fields.Text(
        string='Transaction Info',
        company_dependent=True,
        copy=False,
    )
    qbo_transaction_date = fields.Datetime(
        string='Transaction Date',
        company_dependent=True,
        copy=False,
    )
    qbo_state = fields.Selection(
        selection=[
            ('todo', 'ToDo'),
            ('rejected', 'Rejected'),
            ('pending', 'Pending'),
            ('failed', 'Failed'),
            ('proxy', 'Done'),
        ],
        string='Export Status',
        default='todo',
        company_dependent=True,
        copy=False,
    )
    qbo_update_required = fields.Boolean(
        string='QBO Update Required',
    )

    @staticmethod
    def _get_qbo_unique_identifier():
        raise NotImplementedError()

    @staticmethod
    def _qbo_track_fields():
        raise NotImplementedError()

    def _set_qbo_values(self, *args, **kwargs):
        raise NotImplementedError()

    def _format_duplicate_name(self, *args, **kwargs):
        raise NotImplementedError()

    def _update_records_to_qbo(self, *args, **kwargs):
        raise NotImplementedError()

    def _prepare_qbo_name(self, *args, **kw):
        self.ensure_one()
        return self.name

    def _update_qbo_search_domain(self, domain, map_type):
        """Hook method for defining right domain in finding duplicates."""
        return domain

    def _init_qbo_lib_class(self, map_type):
        return self.map_model._qbo_lib_class[map_type]()

    def _get_qbo_mapping(self, map_type, company_id):
        self.ensure_one()

        map_ids = getattr(self, self.map_model._reverse_field).filtered(
            lambda r: r.qbo_lib_type == map_type and r.company_id.id == company_id
        )

        ensure_currency = self.env.context.get('ensure_qbo_currency')

        if map_ids and ensure_currency:
            for map_id in map_ids:
                map_id._refresh_qbo_mapping_body()

            map_ids = map_ids.filtered(
                lambda x: x._extract_currency_name(lower=True) == ensure_currency.lower()
            )

        return map_ids

    def _get_map_instance_or_raise(self, map_type, company_id, raise_if_not_found=True):
        self.ensure_one()
        instance = self._get_qbo_mapping(map_type, company_id)

        if len(instance) > 1:
            raise ValidationError(_(
                'More than one mapping is available for "%s". '
                'It must be the only one in the current users company "%s".'
                % (self._prepare_qbo_name(), self.env['res.company'].browse(company_id).name)
            ))
        if not instance and raise_if_not_found:
            raise ValidationError(_(
                'Firstly you should perform export of "%s".' % self._prepare_qbo_name()
            ))
        return instance

    def _check_qbo_duplicate(self, company_id, alias='Object', map_type=None):
        self.ensure_one()
        odoo_rel = self.browse()
        domain = [
            ('qbo_name', '=', self.name),
            ('company_id', '=', company_id),
        ]
        dupl_object = self.map_model.search(
            self._update_qbo_search_domain(domain, map_type),
            limit=1,
        )
        if dupl_object:
            odoo_rel = dupl_object.odoo_record

        if dupl_object and odoo_rel:
            raise ValidationError(_(
                '%s with the same name "%s" already exists in "Mapping/%ss". '
                'Moreover it already has a related odoo object. You are trying to make '
                'another one in Intuit but this name must be unique.'
                % (alias, dupl_object._prepare_map_name(), alias)
            ))
        elif dupl_object:
            raise ValidationError(_(
                '%s with the same name "%s" already exists in "Mapping/%ss". '
                'Match if they are the same please.'
                % (alias, dupl_object._prepare_map_name(), alias)
            ))

    def _any_qbo_checking(self, *args, **kw):
        """Hook method for redefining."""
        return True

    def _check_requirements(self, *args, **kw):
        """Hook method for redefining."""
        return True

    def _make_message_post(self, msg, company):
        message = msg + ' [%s]' % company.name
        subscribers = company._prepare_subscribers()
        for record in self:
            record.with_user(SUPERUSER_ID).message_post(body=message, partner_ids=subscribers)

    def _write_info(self, state, info, company_id):
        self.ensure_one()
        company = self.env['res.company'].browse(company_id)

        self.with_company(company).write({
            'qbo_state': state,
            'qbo_transaction_info': info.strip(),
            'qbo_transaction_date': fields.Datetime.now(),
        })

        if state in ERROR_MESSAGES:
            self._make_message_post(ERROR_MESSAGES[state], company)

    def _write_hint(self, message, code, fmt=None):
        self.ensure_one()
        company_id = self.env.context.get('apply_company')

        if not company_id:
            raise ValidationError(_(
                'Company not defined during an error serialization.'
            ))

        hint_info = IntuitResponse.ERROR_HINTS.get(code, '')

        if hint_info and fmt:
            hint_info = hint_info % fmt

        self._write_info('failed', message + hint_info, company_id)

    def _get_map_extra_vals(self, map_model):
        return {
            'is_exported': True,
            map_model._related_field: self.id,
        }

    def _perform_check_duplicate_n_export(self, qbo_lib_model, company):
        map_model = self.map_model
        map_type = qbo_lib_model.qbo_object_name.lower()

        # 1. Check for the previously added record
        condition = self._get_condition_for_check_external(qbo_lib_model)
        result_list, code, = map_model._fetch_qbo_by_query(company, map_type, condition)

        if not IntuitResponse.is_ok(code):
            raise QuickbooksException(result_list, error_code=code)

        # 2. If nothing found - call the original method
        if not result_list:
            ctx = dict(qbo_check_external=False)
            return self.with_context(**ctx)._perform_export_qbo_one(qbo_lib_model, company)

        if len(result_list) > 1:
            raise OdooJobError(_(
                'We found several "%s" with the same number %s: %s. '
                'Before you will be able to continue, you need to remove/rename duplicated '
                'objects in QBO directly. After that re-run the current job.'
            ) % (qbo_lib_model.qbo_object_name, condition, [x.Id for x in result_list]))

        result = result_list[0]
        ctx = dict(apply_company=company.id)
        ex_vals = self._get_map_extra_vals(map_model)

        # 3. Create mapping
        mapping = map_model.with_context(**ctx)._create_qbo_mapping(result, ex_vals)
        if mapping:
            self._write_info('proxy', '', company.id)

        return mapping, code

    def _perform_export_qbo_one(self, qbo_lib_model, company):
        if self.env.context.get('qbo_check_external'):
            return self._perform_check_duplicate_n_export(qbo_lib_model, company)

        fmt = None
        map_model = self.map_model
        map_type = qbo_lib_model.qbo_object_name.lower()
        ex_vals = self._get_map_extra_vals(map_model)
        ctx = {'apply_company': company.id}

        result, code = map_model._save_qbo_one(company, qbo_lib_model)

        if IntuitResponse.is_ok(code):
            mapping = map_model.with_context(**ctx)._create_qbo_mapping(result, ex_vals)

            if mapping:
                self._write_info('proxy', '', company.id)
            return mapping, code

        if code == IntuitResponse.DUPLICATE_NAME:
            ex_vals.pop('is_exported')
            ex_vals['is_imported'] = True
            unique_name = self._get_qbo_unique_identifier()

            fetched_list, code_ = map_model._fetch_qbo_one_by_name(
                company,
                map_type,
                {unique_name: getattr(qbo_lib_model, unique_name)},
            )

            if not IntuitResponse.is_ok(code_):
                self.with_context(**ctx)._write_hint(fetched_list, code_)
                return fetched_list, code_

            if fetched_list:
                fmt = self._format_duplicate_name()
                mapping = map_model.with_context(**ctx)._create_qbo_mapping(fetched_list[0], ex_vals)

                if mapping:
                    self.with_context(**ctx)._write_info('proxy', '', company.id)
                else:
                    code, fmt = IntuitResponse.ODOO_TWIN, None
            else:
                code = IntuitResponse.INTUIT_TWIN

        self.with_context(**ctx)._write_hint(result, code, fmt=fmt)

        return result, code

    def _perform_export_qbo_batch(self, map_type, company):
        records_dict, export_list = {}, []
        map_model = self.map_model
        ex_vals = {'is_exported': True}
        ctx = {'apply_company': company.id}

        unique_name = self._get_qbo_unique_identifier()

        for rec in self:
            qbo_lib_model = rec._init_qbo_lib_class(map_type)
            rec._set_qbo_values(qbo_lib_model, company)
            records_dict[getattr(qbo_lib_model, unique_name)] = rec
            export_list.append(qbo_lib_model)

        if not export_list:
            return False, IntuitResponse.SUCCESS

        result, code = map_model._save_qbo_batch(company, export_list)

        if not IntuitResponse.is_ok(code):
            for rec in self:
                rec.with_context(**ctx)._write_hint(result, code)

            return result, code

        for response_object in result.successes:
            mapping = map_model.with_context(**ctx)._create_qbo_mapping(response_object, ex_vals)

            if mapping:
                record = records_dict.pop(mapping.display_name, self.browse())
                mapping.write({map_model._related_field: record.id})
                record.with_context(**ctx)._write_info('proxy', '', company.id)

        for response_object in result.faults:
            code_, fmt = code, None
            error = response_object.Error[0]
            original_object = response_object.original_object
            response_object_name = getattr(original_object, unique_name)
            record = records_dict.pop(response_object_name, self.browse())

            if int(error.code) == IntuitResponse.DUPLICATE_NAME:
                ex_vals = {
                    'is_imported': True,
                    map_model._related_field: record.id,
                }
                fetched_list, code_ = map_model._fetch_qbo_one_by_name(
                    company,
                    map_type,
                    {unique_name: response_object_name},
                )

                if not IntuitResponse.is_ok(code_):
                    record.with_context(**ctx)._write_hint(fetched_list, code_)
                    continue

                if fetched_list:
                    fmt = record._format_duplicate_name()
                    mapping = map_model.with_context(**ctx)._create_qbo_mapping(fetched_list[0], ex_vals)

                    if mapping:
                        record.with_context(**ctx)._write_info('proxy', '', company.id)
                        continue

                    code_, fmt = IntuitResponse.ODOO_TWIN, None
                else:
                    code_ = IntuitResponse.INTUIT_TWIN

            record.with_context(**ctx)._write_hint(error.Detail, code_, fmt=fmt)

        return result, code

    def _export_qbo_one(self, map_type, company):
        self.ensure_one()

        qbo_lib_model = self._init_qbo_lib_class(map_type)
        self._set_qbo_values(qbo_lib_model, company)

        return self._perform_export_qbo_one(qbo_lib_model, company)

    def _update_one_odoo_to_qbo(self, mapping):
        self.ensure_one()
        company = mapping.company_id

        # Refresh object before update to get actual 'SynkToken' for update
        qbo_lib_model, code = mapping._refresh_qbo_mapping_body()

        if not IntuitResponse.is_ok(code):
            self.with_context(apply_company=company.id)._write_hint(qbo_lib_model, code)
            return qbo_lib_model, code

        self._set_qbo_values(qbo_lib_model, company, updating=True)

        result, code = mapping._save_qbo_one(company, qbo_lib_model)

        if not IntuitResponse.is_ok(code):
            self.with_context(apply_company=company.id)._write_hint(result, code)
            return result, code

        mapping._update_map_one(result)
        self.write({'qbo_update_required': False})

        return result, code

    def _export_qbo_batch(self, map_type, company, ctx_params):
        _logger.info('Export to QBO "%s". Create jobs.' % str(self))

        for rec in self.with_context(company_id=company.id):
            rec._write_info('pending', '', company.id)

            job_kwargs = rec._get_transaction_job_kwargs(map_type)
            rec._mark_failed_jobs_as_cancel(identity_key=job_kwargs['identity_key'])

            rec.with_delay(**job_kwargs)._export_qbo_one(map_type, company)

        return True

    def _validate_qbo_type_export(self, map_type, company):
        _logger.info('Validate "%s" to export "%s".' % (map_type, self.ids))
        self.ensure_one()
        raise_exception = self.env.context.get('raise_exception')
        types_to_export, error_message = [], False

        def _do_raise(info):
            if raise_exception:
                raise ValidationError(info)

        try:
            if self._get_map_instance_or_raise(
                    map_type, company.id, raise_if_not_found=False):
                self._write_info('proxy', '', company.id)
            else:
                types_to_export.append(map_type)
        except ValidationError as ex:
            _do_raise(ex.args[0])
            error_message = ex.args[0]
            self._write_info('rejected', ex.args[0], company.id)

        if not types_to_export:
            return types_to_export, error_message

        try:
            self._any_qbo_checking(map_type, company)
            self._check_requirements(company)
        except ValidationError as ex:
            _do_raise(ex.args[0])
            error_message = ex.args[0]
            types_to_export.remove(map_type)
            self._write_info('rejected', ex.args[0], company.id)

        return types_to_export, error_message

    def _collect_qbo_export_dict(self, map_types, company):
        _logger.info('Collect "%s" export dict "%s".' % (str(map_types), self.ids))

        assert len(map_types) == 1

        name, allowed_ids = self._name, []
        export_dict = defaultdict(lambda: defaultdict(list))
        ctx = {'raise_exception': self.env.context.get('raise_exception')}

        for rec in self:

            types_to_export, error_message = rec.with_context(**ctx)\
                ._validate_qbo_type_export(map_types[0], company)

            for map_type in types_to_export:
                export_dict[name][map_type].append(rec)

            if error_message:
                rec._write_info('rejected', error_message, company.id)
                continue

            allowed_ids.append(rec.id)

        return export_dict, allowed_ids

    def _extract_essential_context(self):
        return tuple()

    def _get_transaction_job_kwargs(self, map_type=False):
        self.ensure_one()

        return dict(
            max_retries=1,
            priority=MODELS_TO_EXPORT.get(self._name, 10),
            identity_key=f'qbo_export_{map_type or self.map_type}_{self}',
            description=f'Export {self._description} "{self.display_name}" to QBO',
            channel=self.sudo().env.ref('quickbooks_sync_online.channel_root_qboch_1').complete_name,
        )

    def _mark_failed_jobs_as_cancel(self, identity_key=None):
        if not identity_key:
            identity_key = self._get_transaction_job_kwargs()['identity_key']

        self.env['queue.job'].search([
            ('state', '=', 'failed'),
            ('identity_key', '=', identity_key),
        ]).button_cancelled()

    def define_transaction_company(self):
        ctx_id = int(self.env.context.get('apply_company', 0))
        return self.env['res.company'].browse(ctx_id) if ctx_id else self.env.company

    @property
    def map_model(self):
        """Get related map model."""
        return self.env[self._qbo_map]

    @property
    def map_types(self):
        """Get list of the qbo-types of the related map model."""
        return self.map_model.qbo_map_list()

    @property
    def map_type(self):
        """Get type of the map-model if it's single."""
        types = self.map_types
        return types[0] if len(types) == 1 else False

    def check_and_perform_export(self, *args, **kwargs):
        """Check an opportunity and make an 'export job'."""
        raise NotImplementedError()

    def to_qbo_json(self):
        raise NotImplementedError()

    def _display_qbo_json(self, name: str, json_str: str):
        wizard = self.env['qbo.help.wizard'].create({
            'information': json.dumps(json_str, indent=8),
        })
        view = self.env.ref('quickbooks_sync_online.qbo_help_wizard_info_form_view')
        return wizard.run_wizard(name, view.id, {})

    def open_current_object(self):
        """
        Open full form of current object.
        There is a standard method 'get_formview_action()',
        but it may be overriden by someone for custom view.
        """
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'self',
            'context': {
                'qbo_todo_list_action': False,
            },
        }
