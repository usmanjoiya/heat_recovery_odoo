from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re



class PlacementConfig(models.Model):
    _name = "placement.config"
    _description = 'Placement Config'


    name = fields.Char(string="Name")

    place_type = fields.Selection(
        [('roof_vents', 'Roof Vents'), ('wall_cowl', 'Wall Cowl')],
        string='Placement'
    )
    diameter = fields.Integer(string="Diameter (mm)")
    quantity = fields.Integer(string="QTY")
    product_id = fields.Many2one('product.product', string="Product")

