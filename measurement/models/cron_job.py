# product_cost_scheduler/models/product_template.py
from odoo import models, api, _

class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def _cron_update_product_sale_prices(self):
        """Scheduled action: update sale price based on cost × category x_factor."""
        templates = self.search([('type', '!=', 'service')])  # skip service type
        for template in templates:
            x_factor = template.categ_id.x_factor or 1.0
            variants = template.product_variant_ids
            for variant in variants:
                variant._compute_product_lst_price()
            if len(variants) == 1:
                variant = variants[0]
                cost = variant.standard_price
                new_sale = cost * x_factor
                template.sudo().write({'list_price': new_sale})
        _logger = self.env['ir.logging']
        _logger.sudo().create({
            'name': _('Product Sale Price Scheduler'),
            'type': 'server',
            'dbname': self.env.cr.dbname,
            'level': 'info',
            'message': _('Updated sale prices for %d templates') % len(templates),
            'path': 'product_cost_scheduler.models.product_template',
            'func': '_cron_update_product_sale_prices',
            'line': '0',
        })
        return True
