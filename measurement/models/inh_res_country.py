from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re


class ResCountry(models.Model):
    _inherit = 'res.country'

    shipping_cost_ids = fields.One2many('shipping.cost','country_id')
