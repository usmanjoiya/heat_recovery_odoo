from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re





class ProductProduct(models.Model):
    _inherit = "product.product"

    product_type = fields.Selection(related="product_tmpl_id.product_type", store=True, readonly=True)
    is_radial_pipe = fields.Boolean('Is Radial Pipe')

    @api.depends('list_price', 'price_extra', 'standard_price')
    @api.depends_context('uom')
    def _compute_product_lst_price(self):
        to_uom = None
        if 'uom' in self.env.context:
            to_uom = self.env['uom.uom'].browse(self.env.context['uom'])

        for product in self:
            if to_uom:
                list_price = product.uom_id._compute_price(product.list_price, to_uom)
            else:
                list_price = product.list_price
            bom_id = product._get_bom_id()
            if bom_id:
                product.lst_price = bom_id.total_sale_price
            elif not product.categ_id:
                product.lst_price = list_price + product.price_extra
            else:
                product.lst_price = product.standard_price * product.categ_id.x_factor if product.categ_id.x_factor else 1

    def _get_bom_id(self):
        template_ids = self.mapped('product_tmpl_id').ids
        domain = ['|', '|', ('byproduct_ids.product_id', 'in', self.ids), ('product_id', 'in', self.ids), '&',
                            ('product_id', '=', False), ('product_tmpl_id', 'in', template_ids)]
        mrp_id = self.env['mrp.bom'].search(domain,limit=1)
        return mrp_id


    def write(self, vals):
        res = super().write(vals)
        if 'standard_price' in vals:
            for component in self:
                bom_lines = self.env['mrp.bom.line'].sudo().search([
                    ('product_id', '=', component.id)
                ])
                boms = bom_lines.mapped('bom_id')

                for bom in boms:
                    main_product = bom.product_id
                    if main_product and hasattr(main_product, 'button_bom_cost'):
                        try:
                            main_product.sudo().button_bom_cost()
                        except Exception:
                            pass
        return res

    # @api.depends('standard_price')
    # @api.onchange('standard_price')
    # def _compute_sale_price_variant(self):
    #     """When cost changes on a variant, update its sale price if category is 'Kit'."""
    #     for product in self:
    #         category = product.categ_id
    #         if product:
    #             if category and category.x_factor:
    #                 product.lst_price = product.standard_price * category.x_factor if category.x_factor else 1

    # @api.depends('standard_price', 'categ_id.x_factor', 'categ_id.name')
    # def _compute_lst_price_from_factor(self):
    #     """Ensure lst_price updates automatically if category is 'Kit'."""
    #     for product in self:
    #         category = product.categ_id
    #         if category and category.name.lower() == 'kit' and category.x_factor:
    #             product.lst_price = product.standard_price * category.x_factor
