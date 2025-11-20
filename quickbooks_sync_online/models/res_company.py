# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import json
import logging
from functools import reduce
from datetime import date, datetime, timedelta

from odoo import models, fields, api, SUPERUSER_ID, _
from odoo.tools import ormcache
from odoo.exceptions import UserError, ValidationError

from .utils import QboCompanyInfo
from .qbo_transaction_mixin import MODELS_TO_EXPORT

_logger = logging.getLogger(__name__)

try:
    from intuitlib.enums import Scopes
    from intuitlib.client import AuthClient
    from intuitlib.utils import generate_token
    from intuitlib.exceptions import AuthClientError

    from quickbooks import QuickBooks
    from quickbooks.objects.preferences import Preferences
    from quickbooks.objects.company_info import CompanyInfo
    from quickbooks.objects.companycurrency import CompanyCurrency
except (ImportError, IOError) as ex:
    _logger.error(ex)


MINOR_VERSION = 63  # Version of the Intuit API.
MODELS_TO_UPDATE = ['res.partner']


class ResCompany(models.Model):
    _inherit = 'res.company'

    qbo_client_id = fields.Char(
        string='Client ID',
    )
    qbo_client_secret = fields.Char(
        string='Client Secret',
    )
    qbo_redirect_uri = fields.Char(
        string='Redirect URI',
        compute='_compute_redirect_uri',
        readonly=True,
    )
    qbo_access_token = fields.Text(
        string='Access Token',
    )
    qbo_refresh_token = fields.Char(
        string='Refresh Token',
    )
    qbo_company_id = fields.Char(
        string='Company ID',
    )
    qbo_company_info = fields.Char(
        string='Company Info',
        compute='_compute_qbo_company_info',
    )
    qbo_is_us_company = fields.Boolean(
        compute='_compute_qbo_company_info',
    )
    qbo_csrf_token = fields.Char(
        string='CSRF',
        readonly=True,
    )
    qbo_environment = fields.Selection(
        selection=[
            ('production', 'Production'),
            ('sandbox', 'Developing'),
        ],
        string='Environment',
        default='production',
    )
    access_token_update_point = fields.Datetime(
        string='Validation access token',
    )
    refresh_token_update_point = fields.Datetime(
        string='Updating refresh token',
    )
    access_token_cron_point = fields.Datetime(
        string='Auto updating access token',
        compute='_compute_access_token_cron_point',
    )
    is_qbo_active = fields.Boolean(
        string='Access Granted',
        compute='_compute_is_qbo_active',
    )
    qbo_auto_export = fields.Boolean(
        string='Automatic Invoice/Bills Export to QBO',
    )
    qbo_payment_sync_in = fields.Boolean(
        string='Automatic Payment Import to Odoo',
    )
    qbo_payment_sync_out = fields.Boolean(
        string='Automatic Payment Export to QBO',
    )
    qbo_cus_pay_point = fields.Char(
        string='Last Customer Payment Point',
        size=30,
        help='The last fetched customer datetime payment point from Quickbooks.',
    )
    qbo_ven_pay_point = fields.Char(
        string='Last Vendor Payment Point',
        size=30,
        help='The last fetched vendor datetime payment point from Quickbooks.',
    )
    qbo_export_date_point = fields.Date(
        string='Export Date Point',
        required=True,
        default=fields.Date.today(),
    )
    qbo_export_limit = fields.Integer(
        string='Export Limit',
        default=10,
        required=True,
    )
    qbo_next_call_point = fields.Datetime(
        string='Next Export Point',
        compute='_compute_next_call',
    )
    qbo_default_stock_valuation_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Default Stock Valuation Account',
        help="""Select here account that will be used for products that are Storable,
        but there 'Inventory Valuation' method is set to Manual.
        We need it cause quickbooks required this account for Stockable products.""",
    )
    qbo_default_write_off_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Default Write-off Account',
        help="""Write-off account is used to record difference between payment downloaded from QBO
        and Invoice total in Odoo in case QBO Invoice is marked as Paid and we also need
        to closed it on Odoo side.""",
    )
    qbo_sync_product = fields.Boolean(
        string='Sync Products',
        default=True,
    )
    qbo_sync_product_category = fields.Boolean(
        string='Sync Products as Category',
    )
    qbo_sync_storable_to_consumable = fields.Boolean(
        string='Sync Storable Product as Consumable',
    )
    qbo_export_out_invoice = fields.Boolean(
        string='Export Customer Invoices (and related Customer Payments)',
        default=True,
    )
    qbo_export_out_refund = fields.Boolean(
        string='Export Customer CreditNotes',
        default=True,
    )
    qbo_export_in_invoice = fields.Boolean(
        string='Export Vendor Bills (and related Vendor Payments)',
        default=True,
    )
    qbo_export_in_refund = fields.Boolean(
        string='Export Vendor Refunds',
        default=True,
    )
    qbo_def_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Default Journal',
    )
    qbo_invoice_tax_included = fields.Boolean(
        string='Send Invoice Tax Included',
        default=False,
    )

    def _compute_is_qbo_active(self):
        for rec in self:
            rec.is_qbo_active = bool(
                rec.qbo_company_id
                and rec.qbo_client_id
                and rec.qbo_client_secret
                and rec.qbo_access_token
                and rec.qbo_refresh_token
            )

    @api.depends('is_qbo_active')
    def _compute_qbo_company_info(self):
        for rec in self:
            if rec.is_qbo_active:
                try:
                    qbo_company = rec._fetch_qbo_company_info()
                    company_info_value = qbo_company.address_format()
                    is_us_company = qbo_company.is_us_company
                except Exception:
                    company_info_value = is_us_company = False
            else:
                company_info_value = is_us_company = False

            rec.qbo_company_info = company_info_value
            rec.qbo_is_us_company = is_us_company

    @property
    def qbo_company_ids(self):
        return self.with_user(SUPERUSER_ID).search([]).filtered(lambda x: x.is_qbo_active)

    def initial_import_from_qbo(self):
        """Make initial import from Intuit."""
        self.env['qbo.map.partner'].get_data_from_qbo()
        self.env['qbo.map.product'].get_data_from_qbo()
        self.env['qbo.map.account'].get_data_from_qbo()
        self.env['qbo.map.tax'].get_data_from_qbo()
        self.env['qbo.map.taxcode'].get_data_from_qbo()
        self.env['qbo.map.term'].get_all_data_from_qbo()
        self.env['qbo.map.payment.method'].get_all_data_from_qbo()
        self.env['qbo.map.department'].get_all_data_from_qbo()

    def ensure_qbo_us_company(self):
        if not self.intuit_is_us_company():
            raise UserError(_('%s: The feature is allowed only for the US companies.') % self.name)

    def external_currency_belong_company(self, currency_name):
        return self.currency_id.name == currency_name

    def _compute_next_call(self):
        cron = self.env.ref(
            'quickbooks_sync_online.trigger_invoice_to_qbo_cron',
            raise_if_not_found=False,
        )
        value = cron.nextcall if cron else False

        for rec in self:
            rec.qbo_next_call_point = value

    def _compute_redirect_uri(self):
        base_url = self.env['ir.config_parameter'].with_user(SUPERUSER_ID).get_param('web.base.url')
        value = '%s/qbo/callback' % base_url

        for rec in self:
            rec.qbo_redirect_uri = value

    @api.depends('access_token_update_point')
    def _compute_access_token_cron_point(self):
        cron = self.env.ref(
            'quickbooks_sync_online.refresh_qbo_access_token_cron',
            raise_if_not_found=False,
        )
        value = cron.nextcall if cron else False

        for rec in self:
            rec.access_token_cron_point = value

    def get_qbo_invoice_allowed_types(self):
        allowed_types = []
        self_su = self.with_user(SUPERUSER_ID)

        if self_su.qbo_export_out_invoice:
            allowed_types.append('out_invoice')
        if self_su.qbo_export_out_refund:
            allowed_types.append('out_refund')
        if self_su.qbo_export_in_invoice:
            allowed_types.append('in_invoice')
        if self_su.qbo_export_in_refund:
            allowed_types.append('in_refund')

        return allowed_types

    def get_qbo_payment_options(self):
        partner_types, payment_types = [], []

        if self.qbo_export_out_invoice:
            partner_types.append('customer')
            payment_types.append('inbound')
        if self.qbo_export_in_invoice:
            partner_types.append('supplier')
            payment_types.append('outbound')

        return partner_types, payment_types

    def _get_qbo_auth_client(self, exclude_access_token=False):
        if not self.qbo_client_id or not self.qbo_client_secret or not self.qbo_redirect_uri:
            raise ValidationError(_(
                '%s: "Client ID" or "Client Secret" or "Redirect URI" are not defined.'
            ) % self.name)

        if not self.qbo_csrf_token:
            self.qbo_csrf_token = f'{generate_token()}.{self.id}'

        params = {
            'client_id': self.qbo_client_id,
            'client_secret': self.qbo_client_secret,
            'redirect_uri': self.qbo_redirect_uri,
            'access_token': self.qbo_access_token,
            'environment': self.get_qbo_env(),
            'state_token': self.qbo_csrf_token,
        }

        if exclude_access_token:
            params.pop('access_token')

        return AuthClient(**params)

    def _generate_qbo_auth_url(self):
        client = self._get_qbo_auth_client(exclude_access_token=True)
        return client.get_authorization_url([Scopes.ACCOUNTING])

    def _prepare_subscribers(self):
        self.ensure_one()
        group = self.env.ref(
            'quickbooks_sync_online.qbo_security_group_manager',
            raise_if_not_found=False,
        )
        if not group:
            return None

        users = self.env['res.users']\
            .search([('groups_id', '=', group.id)])\
            .filtered(lambda r: self.id in r.company_ids.ids)

        return users.mapped('partner_id').ids

    def _check_qbo_auth(self):
        if not self.with_user(SUPERUSER_ID).is_qbo_active:
            raise ValidationError(_('QuickBooks Online is not active for the "%s" company!') % self.name)

    def _check_qbo_product_settings(self):
        self.ensure_one()
        info = None

        if self.qbo_sync_product_category:
            info = _(
                '%s: The operation is not allowed. Your administrator set products synchronization '
                'as synchronization of the corresponding Product category in Quickbooks Settings.'
            )
        elif not self.qbo_sync_product:
            info = _(
                '%s: The operation is not allowed. Your administrator turned off '
                'products synchronization in Quickbooks Settings.'
            )

        if info:
            raise UserError(info % self.name)

    def _check_qbo_tax_settings(self):
        self.ensure_one()
        info = None

        if not self.qbo_sync_product:
            info = _(
                '%s: Auto calculation of QBO taxes cannot be used. '
                'Your administrator turned off products synchronisation in Quickbooks Settings.'
            )

        if info:
            raise UserError(info % self.name)

    def _search_to_qbo_invoices(self, limit=None):
        self.ensure_one()
        invoices = self.with_company(self).env['account.move'].search(
            [
                ('state', '=', 'posted'),
                ('qbo_state', '!=', 'proxy'),
                ('company_id', '=', self.id),
                ('invoice_date', '>=', self.qbo_export_date_point),
                ('move_type', 'in', self.get_qbo_invoice_allowed_types()),
            ],
            limit=limit,
            order='invoice_date,id',
        )
        return invoices

    def _search_to_qbo_payments(self, limit=None):
        self.ensure_one()
        partner_types, payment_types = self.get_qbo_payment_options()

        payments = self.with_company(self).env['account.payment'].search(
            [
                ('state', '=', 'posted'),
                ('qbo_state', '!=', 'proxy'),
                ('company_id', '=', self.id),
                ('partner_type', 'in', partner_types),
                ('date', '>=', self.qbo_export_date_point),
                ('payment_type', 'in', payment_types),
            ],
            limit=limit,
            order='date,id',
        )
        # Filter any refunds
        pay_cust_inv = payments.filtered(
            lambda r: r.partner_type == 'customer' and r.payment_type == 'inbound'
        )
        pay_ven_bill = payments.filtered(
            lambda r: r.partner_type == 'supplier' and r.payment_type == 'outbound'
        )
        return pay_cust_inv + pay_ven_bill

    def _search_to_qbo_update(self, model_name):
        records = self.env[model_name].search([
            ('qbo_update_required', '=', True),
        ])
        return records

    @ormcache(
        'self',
        'self.qbo_refresh_token',
        'self.qbo_access_token',
    )
    def get_quickbooks_api_client(self):
        self.ensure_one()

        if not self.qbo_company_id or not self.qbo_refresh_token:
            raise ValidationError(_(
                '%s: "QBO refresh token" or "QBO company ID" are not defined.'
            ) % self.name)

        params = {
            'auth_client': self._get_qbo_auth_client(),
            'company_id': self.qbo_company_id,
            'refresh_token': self.qbo_refresh_token,
            'minorversion': MINOR_VERSION,
        }

        return QuickBooks(**params)

    def intuit_is_us_company(self):
        qbo_company = self._fetch_qbo_company_info()
        return qbo_company.is_us_company

    def get_qbo_env(self):
        """Using Intuit company for production or developing."""
        if not self.qbo_environment:
            self.qbo_environment = 'production'
        return self.qbo_environment

    @api.model
    def import_intuit_payments_cron(self):
        """Get new payments from Intuit Company."""
        MapPayment, result = self.env['qbo.map.payment'], []

        for company in self.qbo_company_ids.filtered('qbo_payment_sync_in'):
            partner_types, __ = company.get_qbo_payment_options()

            for p_type in set(partner_types):
                map_type = self.env['account.payment']._partner_to_pay_type(partner_type=p_type)

                map_pays = MapPayment.get_intuit_payments(map_type, company)
                result.append((company.name, map_type, map_pays))

        _logger.info('QBO imported payments: %s' % result)
        return result

    @api.model
    def export_intuit_payments_cron(self):
        """Export new payments to the Intuit Company."""

        for company in self.qbo_company_ids.filtered('qbo_payment_sync_out'):
            payments = company._search_to_qbo_payments(limit=company.qbo_export_limit)
            trouble_payments = payments.filtered(lambda r: r.qbo_state != 'todo')

            if len(trouble_payments) >= company.qbo_export_limit:
                info = _(
                    '%s: Export Payments Job has not been created due to there are '
                    'previous exports troubles. Fix them first please.'
                ) % company.name

                _logger.warning(info)
                payments._make_message_post(info, company)
                continue

            map_types = [x._partner_to_pay_type() for x in payments]

            export_dict, __ = payments._collect_qbo_export_dict(list(set(map_types)), company)
            company._process_qbo_export_dict(export_dict)

        return True

    @api.model
    def update_records_to_intuit(self):
        """Update records to the Intuit Company."""
        companies = self.qbo_company_ids
        if not companies:
            return

        for model_name in MODELS_TO_UPDATE:
            records = self._search_to_qbo_update(model_name)

            for map_type in self.env[model_name].map_types:
                for company in companies:
                    records_to_update = self.env[model_name]

                    for rec in records:
                        mapping = rec._get_qbo_mapping(map_type, company.id)

                        if len(mapping) == 1:
                            records_to_update |= rec

                    if records_to_update:
                        records_to_update._update_records_to_qbo(company)

        return True

    @api.model
    def export_invoices_to_qbo_cron(self):
        self._compute_next_call()

        for company in self.qbo_company_ids.filtered('qbo_auto_export'):
            invoices = company._search_to_qbo_invoices(limit=company.qbo_export_limit)
            trouble_invoices = invoices.filtered(lambda r: r.qbo_state != 'todo')

            if len(trouble_invoices) >= company.qbo_export_limit:
                info = _(
                    'Export Invoices Job has not been created due to there are '
                    'previous exports troubles. Fix them first please.'
                )
                _logger.warning(info)
                invoices._make_message_post(info, company)
                continue

            export_dict, __ = invoices._collect_qbo_export_dict(company)
            company._process_qbo_export_dict(export_dict)

        return True

    def print_qbo_settings(self):
        self.ensure_one()
        qbo_company = self._fetch_qbo_company_info()

        wizard = self.env['qbo.help.wizard'].create({
            'information': json.dumps({
                'COMPANY': qbo_company.get_qbo_company_info(),
                'COMPANY CURRENCIES': qbo_company.get_qbo_external_currencies(),
                'COMPANY PREFERENCE': qbo_company.get_qbo_preference(),
            }, indent=8),
        })
        view = self.env.ref('quickbooks_sync_online.qbo_help_wizard_info_form_view')
        return wizard.run_wizard(_('QUICKBOOKS COMPANY SETTINGS'), view.id, {})

    def _update_from_auth_client(self, auth_client: AuthClient) -> bool:
        return self.write({
            'qbo_access_token': auth_client.access_token,
            'qbo_refresh_token': auth_client.refresh_token,
            'access_token_update_point': datetime.now() + timedelta(seconds=auth_client.expires_in),
            'refresh_token_update_point': datetime.now() + timedelta(seconds=auth_client.x_refresh_token_expires_in),
        })

    def _revoke_qbo_access(self):
        if self.qbo_client_id and self.qbo_client_secret and self.qbo_refresh_token:
            try:
                client = self._get_qbo_auth_client()
                client.revoke(token=self.qbo_refresh_token)
            except AuthClientError as ex:
                _logger.error(ex.args)

        res = self.write({
            'qbo_environment': 'production',
            'qbo_client_id': False,
            'qbo_client_secret': False,
            'qbo_company_id': False,
            'qbo_csrf_token': False,
            'qbo_access_token': False,
            'qbo_refresh_token': False,
            'access_token_update_point': False,
            'refresh_token_update_point': False,
            'qbo_export_date_point': date.today(),
            'qbo_auto_export': False,
            'qbo_sync_product': True,
            'qbo_sync_product_category': False,
            'qbo_export_out_invoice': True,
            'qbo_export_out_refund': True,
            'qbo_export_in_invoice': True,
            'qbo_export_in_refund': True,
        })

        self.env.registry.clear_cache()
        _logger.info('QBO access has been revoked.')

        return res

    def _refresh_qbo_access_token(self):
        _logger.info('Refresh QBO access token')

        client = self._get_qbo_auth_client()
        client.refresh(refresh_token=self.qbo_refresh_token)

        res = self._update_from_auth_client(client)
        _logger.info('%s: QBO Access Token has been successfully updated', self.name)
        return res

    def _validate_intuit_company_info(self) -> QboCompanyInfo:
        self.ensure_one()
        self.env.registry.clear_cache()

        qbo_company = self._fetch_qbo_company_info()

        if not qbo_company.validate_country(self.country_id.code):
            raise ValidationError(_(
                '%s: Different countries for Odoo company and QuickBooks company are not allowed!'
            ) % self.name)

        if not qbo_company.validate_home_currency(self.currency_id.name):
            raise ValidationError(_(
                '%s: Different currencies for Odoo company and QuickBooks company are not allowed!'
            ) % self.name)

        return qbo_company

    def check_qbo_connection(self):
        self._validate_intuit_company_info()
        return self._raise_notification('success', f'{self.name}: Connection to QuickBooks is successful!')

    def refresh_qbo_access_token(self):
        for company in self.qbo_company_ids:
            try:
                company._refresh_qbo_access_token()
            except Exception as ex:
                _logger.error('%s: QBO Access Token refresh failed --> %s', company.name, ex.args[0])

    @ormcache(
        'self',
        'self.qbo_refresh_token',
        'self.qbo_access_token',
    )
    def _fetch_qbo_company_info(self):
        try:
            client = self.get_quickbooks_api_client()
            preference = Preferences.get(qb=client)
            currency_list = CompanyCurrency.all(qb=client)
            company_info = CompanyInfo.get(self.qbo_company_id, qb=client)
        except Exception as ex:
            raise ValidationError('%s: %s' % (self.name, ex.args[0]))

        return QboCompanyInfo(preference, company_info, currency_list)

    @staticmethod
    def _raise_notification(ttype: str, message: str):
        """
        :ttype:
            - success
            - warning
        """
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': ttype,
                'sticky': False,
            }
        }

    def _process_qbo_export_dict(self, export_dict):
        """
        export_dict = {
            'res.partner': {
                'vendor': [res.partner(1,), res.partner(6,), res.partner(7,)],
                'customer': [res.partner(2,), res.partner(6,), res.partner(8,)],
            },
            'product.product': {
                'item': [product.product(2,), product.product(14,), product.product(21,)],
            },
            'account.move': {
                'invoice': [account.move(1,), account.move(2,)],
                'creditmemo': [account.move(3,), account.move(5,)],
                'bill': [account.move(4,), account.move(7,)],
                'vendorcredit': [account.move(6,), account.move(8,)],
            },
            'account.payment': {
                'payment': [account.payment(5,), account.payment(8,)],
                'billpayment': [account.payment(2,), account.payment(3,), account.payment(4,)],
            }
        }
        """
        self.ensure_one()

        common_ctx = {}
        if self.env.context.get('qbo_plain_export'):
            common_ctx['test_queue_job_no_delay'] = True

        for _name in MODELS_TO_EXPORT.keys():
            for map_type, model_ids_list in export_dict.get(_name, {}).items():
                grouped_records = self._model_ids_list_split_by_context(model_ids_list)

                for model_ids, ctx_tuple in grouped_records:
                    model_ids.with_context(**common_ctx)._export_qbo_batch(map_type, self, dict(ctx_tuple))

        return True

    def _model_ids_list_split_by_context(self, model_ids_list):
        """
        input:
            model_ids_list = [
                res.partner(33,), res.partner(26,), res.partner(14,), res.partner(27,),
            ]

        output:
            [
                (res.partner(33, 26, 14), ()), (res.partner(27,), (('ensure_qbo_currency', True),)),
            ]

        """
        rec_with_ctx, rec_without_ctx = set(), set()

        for record in model_ids_list:
            ctx_tuple = record._extract_essential_context()

            if ctx_tuple:
                rec_with_ctx.add((record, ctx_tuple))
            else:
                rec_without_ctx.add(record)

        rec_without_ctx = rec_without_ctx\
            and [(reduce(lambda x, y: x + y, set(rec_without_ctx)), tuple())]

        return list(rec_without_ctx) + list(rec_with_ctx)
