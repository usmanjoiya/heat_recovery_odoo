from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re



class StockRule(models.Model):
    _inherit = 'stock.rule'

    @api.model
    def _run_manufacture(self, procurements):
        """
        Extends Odoo's _run_manufacture() to also attach 'part_of_id' products
        as raw materials in Manufacturing Orders linked to a Sale Order.
        """
        result = super()._run_manufacture(procurements)

        for procurement, rule in procurements:
            product = procurement.product_id
            sale_line_id = procurement.values.get('sale_line_id')
            if not sale_line_id:
                continue

            sale_line = self.env['sale.order.line'].browse(sale_line_id)
            order = sale_line.order_id

            # Find the manufacturing order created for this product
            mo_domain = [
                ('product_id', '=', product.id),
                ('origin', '=', procurement.origin or order.name)
            ]
            mo = self.env['mrp.production'].search(mo_domain, limit=1)
            if not mo:
                continue

            # Find related sale order lines whose "part_of_id" = this product
            related_lines = order.order_line.filtered(
                lambda l: l.part_of_id and l.part_of_id == sale_line.product_id
            )

            for comp_line in related_lines:
                self.env['stock.move'].create({
                    'description_picking': comp_line.product_id.display_name,
                    'product_id': comp_line.product_id.id,
                    'product_uom_qty': comp_line.product_uom_qty,
                    'product_uom': comp_line.product_uom_id.id,
                    'location_id': mo.location_src_id.id,
                    'location_dest_id': mo.location_dest_id.id,
                    'raw_material_production_id': mo.id,
                    'company_id': mo.company_id.id,
                    'state': 'draft',
                    'sale_line_id': comp_line.id,
                })

        return result
