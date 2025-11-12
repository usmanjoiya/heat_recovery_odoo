from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    product_diameter = fields.Text(string="Product Diameter (mm)")
    main_kit_product = fields.Boolean('Main Kit Prodcut')
    area_m2_from = fields.Integer()
    area_m2_to = fields.Integer()
    product_type = fields.Selection(
        [
            ('base', 'Base'),
            ('upgraded', 'Upgraded'),
            ('premium', 'Premium'),
        ],
        string="Product Type"
    )

    m3_h = fields.Float(string="Flow Rate (m³/h)")

    prod_capacity = fields.Float(string="Product Capacity")
