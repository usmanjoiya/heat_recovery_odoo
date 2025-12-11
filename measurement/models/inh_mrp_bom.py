from odoo import _, models, fields, api

class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    total_sale_price = fields.Float(string="Total Sale Price", compute="_compute_total_sale_price", store=False)

    @api.depends('bom_line_ids', 'bom_line_ids.product_id', 'bom_line_ids.product_qty')
    def _compute_total_sale_price(self):
        for rec in self:
            total = 0.0
            for line in rec.bom_line_ids:
                price = line.product_id.lst_price or 0.0
                qty = line.product_qty or 0.0
                total += price * qty
            rec.total_sale_price = total
