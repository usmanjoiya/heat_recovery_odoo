# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging
from datetime import datetime as dt
from collections import namedtuple
from dateutil import parser

from odoo import models, fields, _
from odoo.exceptions import UserError, ValidationError

from ..utils import QboClass, IntuitResponse

_logger = logging.getLogger(__name__)

try:
    from quickbooks.objects.payment import Payment
    from quickbooks.objects.billpayment import BillPayment
    from quickbooks.helpers import qb_datetime_format
except (ImportError, IOError) as ex:
    _logger.error(ex)


INVOICE = 'Invoice'
CREDITMEMO = 'CreditMemo'
BILL = 'Bill'
VENDORCREDIT = 'VendorCredit'

DATEFIELD_TO_INVOICE_TYPE = {
    'qbo_cus_pay_point': ('invoice', 'creditmemo'),
    'qbo_ven_pay_point': ('bill', 'vendorcredit'),
}

PAYMENT_TYPE_TO_DATEFIELD = {
    'payment': 'qbo_cus_pay_point',
    'billpayment': 'qbo_ven_pay_point',
}

PayTuple = namedtuple('PayTuple', 'txn_id txn_type amount')


class QboMapPayment(models.Model):
    _name = 'qbo.map.payment'
    _inherit = 'qbo.map.mixin'
    _description = 'Qbo Map Payment'

    _qbo_lib_class = QboClass(Payment, BillPayment)

    _res_model = 'account.payment'
    _related_field = 'payment_id'
    _reverse_field = 'qbo_payment_ids'
    _map_routes = {
        'qbo_name': ('["PaymentRefNum"]', ''),
        'currency_ref': ('["CurrencyRef"]["value"]', ''),
        'pay_method': ('["PaymentMethodRef"]["value"]', ''),
        'txn_date': ('["TxnDate"]', ''),
        'sync_token': ('["SyncToken"]', '0'),
        'update_point.update_time_str': ('["MetaData"]["LastUpdatedTime"]', ''),
        'update_point.create_time_str': ('["MetaData"]["CreateTime"]', ''),
    }

    txn_id = fields.Many2one(
        comodel_name='qbo.map.account.move',
        string='Parent Invoice',
        ondelete='restrict',
    )
    invoice_id = fields.Many2one(
        related='txn_id.invoice_id',
    )
    txn_type = fields.Selection(
        related='txn_id.qbo_lib_type',
        string='Invoice Type',
    )
    txn_amount = fields.Char(
        string='Amount',
    )
    txn_date = fields.Char(
        string='Date',
    )
    pay_method = fields.Char(
        string='Payment Method',
    )
    currency_ref = fields.Char(
        string='Currency',
    )
    payment_id = fields.Many2one(
        comodel_name=_res_model,
        string='ODOO Payment',
    )
    sync_token = fields.Char(
        string='Sync Token',
        size=3,
        default='0',
        help='Sync token increments after payment update.',
    )
    update_point = fields.Datetime(
        string='Update Time Point',
        readonly=True,
    )

    def try_to_map(self, *args, **kw):
        raise NotImplementedError()

    @staticmethod
    def datetime_field_name(map_type):
        return PAYMENT_TYPE_TO_DATEFIELD[map_type]

    def register_payment(self, delayable=False):
        mappings = self.filtered('txn_id.invoice_id').sorted(lambda r: r.update_point or dt.now())
        timestamp = dt.now().strftime('%m/%d/%Y, %H:%M:%S')

        results = []
        for idx, mapping in enumerate(mappings, start=1):
            mapping_ = mapping.with_context(company_id=self.company_id.id)

            if delayable:
                mapping_ = mapping_.with_delay(
                    priority=20,
                    description=f'{timestamp}: Register QBO payment ({idx}): [{mapping.qbo_id}] {mapping.qbo_name}',
                )

            res = mapping_._register_payment()
            results.append(res)

        return results

    def get_intuit_payments(self, map_type, company):
        """Getting the latest payments from the Intuit Company."""
        start_point = self.get_fetch_point(map_type, company)

        if not start_point:
            _logger.info(_(
                'There are no exported invoices for payments synchronizations for "%s".'
                % company.name
            ))
            return False

        condition = self._get_fetch_condition(start_point)
        result, code, = self._fetch_qbo_by_query(company, map_type, condition)

        if not IntuitResponse.is_ok(code):
            _logger.error(result)
            return False

        if not result:
            _logger.info('There are no new Intuit payments for the "%s".', company.name)
            return False

        payment_mappings = self._handle_received_records(result, map_type, company.id)

        self._update_fetch_point(result, map_type, company)

        if self.env.context.get('not_register_payment'):
            return payment_mappings

        payment_mappings.register_payment(delayable=True)

        return payment_mappings

    def get_payment_journal_id(self):
        self.ensure_one()

        if self.pay_method:
            journal = self.env['qbo.map.payment.method'].search([
                ('qbo_id', '=', self.pay_method),
                ('company_id', '=', self.company_id.id),
            ], limit=1).journal_id

            if not journal:
                raise ValidationError(_(
                    '%s: It is not possible to register payment in Odoo. Please, '
                    'define in the menu [QuickBooks Online --> Mapping --> Payment Methods] '
                    '"ODOO Journal" for the "%s" payment method.' % (self.company_id.name, self.pay_method)
                ))
        else:
            journal = self.company_id.qbo_def_journal_id

            if not journal:
                raise ValidationError(_(
                    '%s: It is not possible to register payment in Odoo. Please, '
                    'spicify in the menu [QuickBooks Online --> Configuration --> Settings] '
                    '"Default Payment Journal" field.' % self.company_id.name
                ))

        return journal.id

    def get_fetch_point(self, map_type, company):
        date_field = self.datetime_field_name(map_type)
        date_field_value = getattr(company, date_field)

        if self._parse_datetime_from_str(date_field_value):
            return date_field_value

        condition = self._get_datetime_condition(date_field, company.id)

        self.env.cr.execute(condition)
        result = self.env.cr.fetchone()
        point = result[0] and result[0].replace(minute=0, hour=0, second=0, microsecond=0)

        return self._convert_datetime_to_str(point)

    def unlink(self):
        if self.filtered('payment_id'):
            raise UserError(_(
                'Registered payments "%s" may not be deleted!' % self.filtered('payment_id').ids
            ))
        return super(QboMapPayment, self).unlink()

    @staticmethod
    def _get_datetime_condition(date_field, company_id):
        query_string = """
        SELECT MIN(create_date) FROM qbo_map_account_move
        WHERE company_id = %s AND (qbo_lib_type = '%s' OR qbo_lib_type = '%s')
        """
        return query_string % (company_id, *DATEFIELD_TO_INVOICE_TYPE[date_field])

    @staticmethod
    def _get_fetch_condition(*datetime_point):
        return "MetaData.LastUpdatedTime >= '%s' ORDERBY MetaData.LastUpdatedTime ASC" % datetime_point

    @staticmethod
    def _parse_pay_line(line):
        try:
            txn = line['LinkedTxn']
            map_invoice_id = txn[0]['TxnId']
            invoice_type = txn[0]['TxnType'].lower()
            amount = line['Amount']
        except Exception as ex:
            _logger.error(ex)
            return []

        line_args = [map_invoice_id, invoice_type, amount]
        return line_args if all(line_args[1:]) else []

    @staticmethod
    def _parse_datetime_from_str(dtime_str):
        try:
            return parser.isoparse(dtime_str).replace(tzinfo=None)
        except Exception:
            return False

    @staticmethod
    def _convert_datetime_to_str(dtime_obj):
        try:
            return qb_datetime_format(dtime_obj)
        except Exception:
            return False

    def _parse_transaction_lines(self, object_dict: dict) -> PayTuple:
        line_args_list = [
            self._parse_pay_line(line) for line in object_dict.get('Line', [])
        ]
        return [PayTuple(*args) for args in filter(None, line_args_list)]

    def _create_qbo_mapping(self, qbo_lib_model, extra_vals, **kw):
        """Redefined method from abstract model."""
        company_id = self.env.context.get('apply_company')
        if not company_id:
            raise ValidationError(_('Company not defined during creating mapping.'))

        if self.env.context.get('force_save_qbo_record'):
            extra_vals.update({
                'txn_id': self.env.context.get('_txn_id', False),
                'txn_amount': self.env.context.get('_txn_amount', False),
            })
            return super(QboMapPayment, self)._create_qbo_mapping(qbo_lib_model, extra_vals, **kw)

        qbo_id = qbo_lib_model.Id
        map_type = qbo_lib_model.qbo_object_name.lower()

        base_vals = {
            'qbo_id': qbo_id,
            'qbo_lib_type': map_type,
            'company_id': company_id,
            'qbo_object': qbo_lib_model.to_json(),
            **extra_vals,
            **self._parse_values_from_lib_obj(qbo_lib_model),
        }
        mapping_values = self._adjust_map_values(base_vals, qbo_lib_model)

        previous_payments = self.search([
            ('qbo_id', '=', qbo_id),
            ('qbo_lib_type', '=', map_type),
            ('company_id', '=', company_id),
        ])

        transaction_list = self._parse_transaction_lines(qbo_lib_model.to_dict())

        if previous_payments:
            tokens_list = [0] + previous_payments.filtered('sync_token').mapped('sync_token')

            if int(mapping_values['sync_token']) <= max(map(int, tokens_list)):
                # Return if `sync_token` was not incremented.
                _logger.info(
                    'QBO Payment was skipped: %s (qbo_id=%s; map_type=%s; sync_token=%s) --> '
                    'Previous payments found: (ids=%s; sync_tokens=%s; amounts=%s)',
                    mapping_values['qbo_name'],
                    qbo_id,
                    map_type.capitalize(),
                    mapping_values['sync_token'],
                    previous_payments.ids,
                    previous_payments.mapped('sync_token'),
                    previous_payments.mapped('txn_amount'),
                )
                return self.browse()

            to_create_list = self._collect_vals_from_transactions(
                previous_payments,
                transaction_list,
                mapping_values,
            )
        else:
            to_create_list = [
                self._collect_single_pay_vals(pay, mapping_values) for pay in transaction_list
            ]

        to_create_list = [x for x in to_create_list if x]

        if not to_create_list:
            return self.browse()

        mappings = self.create(to_create_list)
        _logger.info('(%s) QBO %s mapping\'s were created --> %s' % (company_id, map_type, mappings))

        return mappings

    def _collect_vals_from_transactions(self, previous_pays, txn_list, vals):
        def _update_vals(pay):
            exists_pays = previous_pays.filtered(
                lambda r: r.txn_id.qbo_id == pay.txn_id and r.txn_type == pay.txn_type
            )
            paid_sum = sum(map(float, exists_pays.mapped('txn_amount')))
            balance_amount = round(float(pay.amount) - paid_sum, 2) if exists_pays else pay.amount

            return {**vals, 'txn_amount': str(balance_amount)}

        return [
            self._collect_single_pay_vals(pay, _update_vals(pay)) for pay in txn_list
        ]

    def _collect_single_pay_vals(self, pay: PayTuple, vals: dict) -> dict:
        map_invoice = self.env['qbo.map.account.move'].search([
            ('invoice_id', '!=', False),
            ('qbo_id', '=', pay.txn_id),
            ('payment_state', 'not in', ('paid', 'in_payment')),
            ('qbo_lib_type', '=', pay.txn_type),
            ('company_id', '=', vals['company_id']),
        ], limit=1)

        if not map_invoice:
            return {}

        _map_vals = {
            'txn_id': map_invoice.id,
            'txn_amount': pay.amount,
            **vals,  # `vals` have to be unpacked right here
        }
        return _map_vals

    def _adjust_map_values(self, vals, qbo_lib_model):
        res = super(QboMapPayment, self)._adjust_map_values(vals, qbo_lib_model)

        time_to_convert = res['update_point']['update_time_str'] or res['update_point']['create_time_str']

        res['update_point'] = self._parse_datetime_from_str(time_to_convert)

        if qbo_lib_model.qbo_object_name == 'BillPayment':
            res['qbo_name'] = qbo_lib_model.DocNumber

        return res

    def _parse_writeoff_account_vals(self, map_invoice):
        vals, pay_ids = {}, []

        if map_invoice.qbo_object_name == INVOICE:
            pay_ids = [
                pay.TxnId for pay in map_invoice.LinkedTxn if pay.TxnType == 'Payment'
            ]
        elif map_invoice.qbo_object_name == BILL:
            pay_ids = [
                pay.TxnId for pay in map_invoice.LinkedTxn if pay.TxnType == 'BillPaymentCheck'
            ]
        elif map_invoice.qbo_object_name == VENDORCREDIT:
            pass  # TODO: It seems there is no smt related to payments
        elif map_invoice.qbo_object_name == CREDITMEMO:
            pass  # TODO: CreditMemo object has no LinkedTxn list

        pay_ids.sort(key=int)

        if pay_ids and self.qbo_id == pay_ids[-1] and map_invoice.Balance == 0:
            self.txn_id.qbo_object = map_invoice.to_json()

            write_off_account_id = self.company_id.qbo_default_write_off_account_id

            if not write_off_account_id:
                info = _(
                    'It\'s not possible to register payment in Odoo. '
                    'Specify `Default Write-off Account` in the module settings.'
                )
                raise ValidationError(info)

            vals.update({
                'payment_difference_handling': 'reconcile',
                'writeoff_account_id': write_off_account_id.id,
            })

        return vals

    def _register_payment(self):
        if self.payment_id:
            info = _('QBO payment (id=%s; qbo_id=%s) was skipped. Is already registered.') % (self.id, self.qbo_id)
            return False, info

        invoice_mapping = self.txn_id

        if not invoice_mapping or invoice_mapping.payment_state in ('paid', 'in_payment'):
            info = _('QBO payment (id=%s; qbo_id=%s) was skipped. Odoo invoice is paid.') % (self.id, self.qbo_id)
            return False, info

        qb_invoice, code = invoice_mapping.fetch_qbo_one()

        if not IntuitResponse.is_ok(code):
            raise ValidationError(f'{code}: {qb_invoice}')

        from_cur = self.env['res.currency'].search([
            ('name', '=', self.currency_ref),
        ], limit=1)

        values = {
            'amount': abs(float(self.txn_amount)),
            'journal_id': self.get_payment_journal_id(),
            'currency_id': (from_cur or self.invoice_id.currency_id).id,
            'payment_date': dt.strptime(self.txn_date, '%Y-%m-%d').date(),
            **self._parse_writeoff_account_vals(qb_invoice)
        }

        wizard = self.env['account.payment.register']\
            .with_context(
                active_model=self.invoice_id._name,
                active_ids=self.invoice_id.ids,
            ).create(values)

        payment = wizard._create_payments()

        self.payment_id = payment.id
        self.invoice_id.with_company(self.company_id).write({
            'qbo_transaction_info': False,
        })
        return payment, payment.name

    def _update_fetch_point(self, lst, map_type, company):
        filter_list = []

        for rec in lst:
            metadata = rec.MetaData

            if isinstance(metadata, dict):
                value = metadata.get('LastUpdatedTime')
            else:
                value = getattr(metadata, 'LastUpdatedTime', False)

            if value:
                filter_list.append(value)

        if filter_list:
            company.write({
                self.datetime_field_name(map_type): filter_list[-1],
            })
