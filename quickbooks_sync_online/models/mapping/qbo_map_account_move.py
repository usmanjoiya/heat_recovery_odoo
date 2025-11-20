# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging

from odoo import fields, models

from ..utils import QboClass

_logger = logging.getLogger(__name__)

try:
    from quickbooks.objects.bill import Bill
    from quickbooks.objects.invoice import Invoice
    from quickbooks.objects.creditmemo import CreditMemo
    from quickbooks.objects.vendorcredit import VendorCredit
except (ImportError, IOError) as ex:
    _logger.error(ex)


class QboMapAccountMove(models.Model):
    _name = 'qbo.map.account.move'
    _inherit = 'qbo.map.mixin'
    _description = 'Qbo Map Account Move'

    _qbo_lib_class = QboClass(Invoice, CreditMemo, Bill, VendorCredit)

    _res_model = 'account.move'
    _related_field = 'invoice_id'
    _reverse_field = 'qbo_invoice_ids'
    _map_routes = {
        'qbo_name': ('["DocNumber"]', ''),
        'total_amt': ('["TotalAmt"]', 0),
        'invoice_link': ('["InvoiceLink"]', ''),
        'total_tax': ('["TxnTaxDetail"]["TotalTax"]', 0),
    }

    total_amt = fields.Float(
        string='Amount Total',
        readonly=True,
    )
    total_tax = fields.Float(
        string='Tax Total',
        readonly=True,
    )
    qbo_tax_ids = fields.Many2many(
        comodel_name='qbo.map.tax',
        string='QBO Taxes',
    )
    invoice_link = fields.Char(
        string='Invoice Link',
        readonly=True,
    )
    invoice_id = fields.Many2one(
        comodel_name=_res_model,
        string='ODOO Invoice',
        domain='[("company_id", "=", company_id)]',
    )
    partner_id = fields.Many2one(
        related='invoice_id.partner_id',
    )
    payment_state = fields.Selection(
        related='invoice_id.payment_state',
    )
    payment_ids = fields.One2many(
        comodel_name='qbo.map.payment',
        inverse_name='txn_id',
        string='Map Payments',
    )
    invoice_map_line_ids = fields.One2many(
        comodel_name='qbo.map.invoice.line',
        inverse_name='invoice_map_id',
        string='Map Invoice Lines',
    )

    def try_to_map(self, *args, **kw):
        raise NotImplementedError()

    def _prepare_map_lines(self, qbo_lib_model):
        res = super(QboMapAccountMove, self)._prepare_map_lines(qbo_lib_model)
        for data in res:
            data['invoice_map_id'] = self.id
        return res

    def _recompute_map_lines(self):
        # 0. Unlink old values for recomputing
        self.qbo_tax_ids = [(6, 0, [])]
        self.invoice_map_line_ids.unlink()

        qbo_lib_model = self.instance_from_json()
        # 1. Parse taxes
        map_tax = self._parse_map_tax_ids(qbo_lib_model, self.company_id.id)
        self.qbo_tax_ids = [(6, 0, map_tax.ids)]
        # 2. Create map-lines
        vals_list = self._prepare_map_lines(qbo_lib_model)
        self.env['qbo.map.invoice.line'].create(vals_list)


class QboMapInvoiceLine(models.Model):
    _name = 'qbo.map.invoice.line'
    _inherit = 'qbo.tax.line.abstract'
    _description = 'Qbo Map Invoice Line'

    invoice_map_id = fields.Many2one(
        comodel_name='qbo.map.account.move',
        string='Map Invoice',
        required=True,
    )
