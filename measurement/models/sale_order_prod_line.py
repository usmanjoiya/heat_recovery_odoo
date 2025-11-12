from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re



class SaleOrderProductLine(models.Model):
    _name = 'sale.order.product.line'
    _description = 'Filtered Products for Sale Order'

    sale_id = fields.Many2one('sale.order', string="Sale Order", ondelete="cascade")
    product_id = fields.Many2one('product.product', string="Product")
    product_diameter = fields.Text(string="Diameter (mm)")
    product_type = fields.Selection([
        ('base', 'Base'),
        ('upgraded', 'Upgraded'),
        ('premium', 'Premium'),
    ], string="Product Type")
    m3_h = fields.Float(string="M³/h")
    prod_capacity = fields.Float(string="Capacity")
    already_link = fields.Boolean(string='Linked', compute='_already_link_on_sale')

    sale_price = fields.Float(string="Sale Price")
    discount = fields.Float(string="Discount (%)", default=0.0)
    discounted_price = fields.Float(string="Discounted Price")

    def _already_link_on_sale(self):
        for line in self:
            link = False
            if line.sale_id and line.sale_id.state in ('sale', 'cancel'):
                link = True
            elif line.sale_id and line.sale_id.order_line:
                get_product = line.sale_id.order_line.filtered(lambda l: l.product_id.id == line.product_id.id)
                if get_product:
                    link = True
            line.already_link = link



    def action_add_to_order_line(self):
        """Add the selected product to the sale order lines."""
        for rec in self:
            if not rec.sale_id:
                raise UserError("No related Sale Order found.")
            if not rec.product_id:
                raise UserError("No product selected to add.")

            order = rec.sale_id

            # Check if the product is already in order lines
            existing_line = order.order_line.filtered(lambda l: l.product_id.id == rec.product_id.id)
            kit_exist = order.order_line.filtered(lambda l: l.product_id.main_kit_product == True)
            if existing_line:
                # If already exists, increase quantity
                existing_line.product_uom_qty += 1
            else:
                # Otherwise create a new sale.order.line
                self.env['sale.order.line'].create({
                    'order_id': order.id,
                    'product_id': rec.product_id.id,
                    'name': rec.product_id.display_name,
                    'product_uom_qty': 1,
                    'price_unit': rec.sale_price,
                    'tax_ids': [(6, 0, rec.product_id.taxes_id.ids)],
                    'part_of_id': kit_exist[0].product_id.id if kit_exist else False,
                })
