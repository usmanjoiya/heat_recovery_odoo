from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re


class ResCountryState(models.Model):
    _inherit = 'res.country.state'

    name = fields.Char(string='Postal code')
    postal_ids = fields.One2many('postal.code', 'state_id')
    cost = fields.Float(String='Cost')
