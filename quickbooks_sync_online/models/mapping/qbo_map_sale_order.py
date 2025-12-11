# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging

from odoo import fields, models

from ..utils import QboClass

_logger = logging.getLogger(__name__)

try:
    from quickbooks.objects.salesreceipt import SalesReceipt
except (ImportError, IOError) as ex:
    _logger.error(ex)


class QboMapSaleOrder(models.Model):
    _name = 'qbo.map.sale.order'
    _inherit = 'qbo.map.mixin'
    _description = 'Qbo Map Sale Order'

    _qbo_lib_class = QboClass(SalesReceipt)

    _res_model = 'sale.order'
    _related_field = 'order_id'
    _reverse_field = 'qbo_sale_ids'
    _map_routes = {
        'qbo_name': ('["DocNumber"]', ''),
        'total_tax': ('["TxnTaxDetail"]["TotalTax"]', ''),
    }

    order_id = fields.Many2one(
        comodel_name=_res_model,
        string='ODOO Sale Order',
        domain='[("company_id", "=", company_id)]',
    )
    partner_id = fields.Many2one(
        related='order_id.partner_id',
    )
    qbo_tax_ids = fields.Many2many(
        comodel_name='qbo.map.tax',
        string='QBO Taxes',
    )
    total_tax = fields.Char(
        string='Total Tax',
    )
    order_map_line_ids = fields.One2many(
        comodel_name='qbo.map.sale.order.line',
        inverse_name='order_map_id',
        string='Map Order Lines',
    )

    def _get_existing_ids(self, *args, **kwargs):
        """
        This is just a dummy-method now.
        No need to check existing records during creating mapping.
        By and large no need to store mapping.
        """
        return []

    def _adjust_map_values(self, map_vals, qbo_lib_model):
        res = super(QboMapSaleOrder, self)._adjust_map_values(map_vals, qbo_lib_model)
        map_tax = self._parse_map_tax_ids(qbo_lib_model, map_vals.get('company_id'))
        res['qbo_tax_ids'] = [(6, 0, map_tax.ids)]
        return res

    def _post_create_map(self, qbo_lib_model):
        vals_list = self._prepare_map_lines(qbo_lib_model)
        self.env['qbo.map.sale.order.line'].create(vals_list)

    def _prepare_map_lines(self, qbo_lib_model):
        res = super(QboMapSaleOrder, self)._prepare_map_lines(qbo_lib_model)
        for data in res:
            data['order_map_id'] = self.id
        return res

    def try_to_map(self, *args, **kw):
        raise NotImplementedError()


class QboMapSaleOrderLine(models.Model):
    _name = 'qbo.map.sale.order.line'
    _inherit = 'qbo.tax.line.abstract'
    _description = 'Qbo Map Sale Order Line'

    order_map_id = fields.Many2one(
        comodel_name='qbo.map.sale.order',
        string='Map Order',
        ondelete='cascade',
        required=True,
    )
