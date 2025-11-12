from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re


class PostalCode(models.Model):
    _name = 'postal.code'
    _description = 'Portal Code'

    name = fields.Char(string='Postal code')
    state_id = fields.Many2one('res.country.state')
