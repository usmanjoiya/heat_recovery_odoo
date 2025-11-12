from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re



class ProductCategory(models.Model):
    _inherit = 'product.category'

    x_factor = fields.Float(
        string='X Factor',
        default=2.25,
        help='Custom multiplier factor for this category'
    )
