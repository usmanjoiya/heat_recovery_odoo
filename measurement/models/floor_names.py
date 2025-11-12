from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re


class FloorNames(models.Model):
    _name = 'floor.names'
    _description = 'Floor Names'
    _rec_name = "floor_name"

    floor_name = fields.Char(string='Floor Name')
