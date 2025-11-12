from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re

class DwellingVentilation(models.Model):
    _name = 'dwelling.ventilation'
    _description = 'Whole Dwelling Ventilation'

    bedroom_no = fields.Integer(string="Bedrooms")
    min_vent_rate = fields.Float(string='Minimum Ventilation Rates (l/s)')
