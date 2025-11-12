from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re



class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    part_of_id = fields.Many2one('product.product' ,string="Part Of")
    price_unit = fields.Float(
        string="Unit Price",
        compute='_compute_price_unit',
        digits='Product Price',
        store=True, readonly=False, required=True, precompute=True)

    price_subtotal = fields.Monetary(
        string="Subtotal",
        compute='_compute_amount',
        store=True, precompute=True)


    @api.depends('product_id', 'product_uom_id', 'product_uom_qty')
    def _compute_price_unit(self):
        def has_manual_price(line):
            currency = (
                    line.currency_id
                    or line.company_id.currency_id
                    or line.env.company.currency_id
            )
            return currency.compare_amounts(line.technical_price_unit, line.price_unit)

        force_recompute = self.env.context.get('force_price_recomputation')
        for line in self:
            # Skip unwanted cases, same as base
            if not line.order_id or line.is_downpayment or line._is_global_discount():
                continue

            if (
                    (not force_recompute and has_manual_price(line))
                    or line.qty_invoiced > 0
                    or (line.product_id.expense_policy == 'cost' and line.is_expense)
            ):
                continue

            line = line.with_context(sale_write_from_compute=True)

            if not line.product_uom_id or not line.product_id:
                line.price_unit = 0.0
                line.technical_price_unit = 0.0
            else:
                # 💡 Override logic: Use lst_price instead of pricelist or computed value
                price = line.product_id.lst_price or 0.0

                # Adjust for UoM if needed (since lst_price is per product’s UoM)
                if (
                        line.product_uom_id
                        and line.product_uom_id != line.product_id.uom_id
                ):
                    price = line.product_id.uom_id._compute_price(price, line.product_uom_id)

                line.price_unit = price
                line.technical_price_unit = price
