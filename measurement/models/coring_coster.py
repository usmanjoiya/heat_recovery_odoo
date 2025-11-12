from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re



class CoringCoster(models.Model):
    _name = 'coring.coster'
    _description = 'Coring Coster'

    name = fields.Char(string="Name")
    core_size = fields.Char(string="Core Size")
    amount = fields.Float(string="Amount")
    cost = fields.Float(string="Cost")
    sub_total = fields.Integer(string="Sub Total")
    total_cost = fields.Integer(string="Total")
