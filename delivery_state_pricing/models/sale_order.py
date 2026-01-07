from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def set_delivery_line(self, carrier, amount):
        """Override to set delivery line quantity and price from context."""
        pallets = self.env.context.get('pallets', 0)
        price = self.env.context.get('delivery_price', 0)

        res = super().set_delivery_line(carrier, amount)

        delivery_line = self.order_line.filtered('is_delivery')
        if delivery_line:
            if pallets > 0:
                delivery_line.product_uom_qty = pallets
            if price > 0:
                delivery_line.price_unit = price

        return res
