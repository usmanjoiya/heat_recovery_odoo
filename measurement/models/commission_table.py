from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re


class CommissionTable(models.Model):
    _name = 'commission.table'
    _description = 'COMMISSIONING TABLE (l/s)'
    _order = 'sequence, id'  # ensures sorting by sequence

    sequence = fields.Integer(string='Sequence',default=10)

    order_id = fields.Many2one('sale.order',string='Sale Order',ondelete='cascade')
    floor_id = fields.Many2one('floor.names',string="Floor")

    point_id = fields.Many2one('commission.point', string='Point')
    extract = fields.Char(related="point_id.extract")
    high = fields.Float(related="point_id.high" ,string="Point")
    boost = fields.Float(string='Boost')
    boost2 = fields.Float(string='Boost 2', compute='_compute_boost2', store=True)
    trickle = fields.Float(string='Trickle')
    trickle2 = fields.Float(string='Trickle 2',compute='_compute_trickle2', store=True)
    drops = fields.Integer(string='Drops', compute='_compute_drops', store=True)
    ducts = fields.Integer(string='75mm Ducts', compute='_compute_ducts', store=True)

    @api.depends('order_id.correct_rate', 'high', 'order_id.extract_rate')
    def _compute_trickle2(self):
        for record in self:
            if record.order_id and record.order_id.extract_rate:
                record.trickle2 = record.order_id.correct_rate * (record.high / record.order_id.extract_rate)
            else:
                record.trickle2 = 0.0

    @api.depends('high','trickle2')
    def _compute_boost2(self):
        for record in self:
            record.boost2 = max(record.high,record.trickle2 * 1.1)

    @api.depends('trickle2')
    def _compute_drops(self):
        for rec in self:
            if rec.trickle2 < 1:
                rec.drops = 0
            elif 1 <= rec.trickle2 <= 12.9:
                rec.drops = 1
            elif rec.trickle2 >= 13:
                rec.drops = 2
            else:
                rec.drops = 0

    @api.depends('trickle2')
    def _compute_ducts(self):
        for rec in self:
            if rec.trickle2 < 1:
                rec.ducts = 0
            elif 1 <= rec.trickle2 <= 4:
                rec.ducts = 1
            elif 4 < rec.trickle2 <= 12.9999:
                rec.ducts = 2
            elif rec.trickle2 >= 13:
                rec.ducts = 4
            else:
                rec.ducts = 0
