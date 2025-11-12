from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re





class CalculatorTool(models.Model):
    _name = 'calculator.tool'
    _description = 'Calculator Tool'

    order_id = fields.Many2one('sale.order', string='Sale Order', ondelete='cascade')
    milage_one_way = fields.Integer(string="MILAGE ONE WAY")
    nights = fields.Integer(string="NIGHTS")
    coring = fields.Float(string="CORING")
    commission = fields.Selection(
        [
            ('0', '0'),
            ('175', '175'),
            ('250', '250')],
        string='COMMISSIONING'
    )
    men_needed = fields.Integer(string="MEN NEEDED")
    days = fields.Integer(string="DAYS")
    trip_needed = fields.Integer(string="TRIPS NEEDED")
    base_cost = fields.Float(string="BASE COST")
    profit = fields.Float(string="PROFIT")
    total = fields.Float(string="TOTAL")

