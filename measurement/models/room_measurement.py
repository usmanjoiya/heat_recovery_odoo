from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re


class RoomMeasurement(models.Model):
    _name = 'room.measurement'
    _description = 'Room Measurement'

    order_id = fields.Many2one('sale.order',string='Sale Order',ondelete='cascade')

    supply = fields.Char(string='Supply', compute='_compute_supply_name', store=True)
    supply_boost2 = fields.Float(string='Boost2', compute='_compute_supply_boost2', store=True)
    supply_trickle2 = fields.Float(string='Trickle2', compute='_compute_supply_trickle2', store=True)
    supply_drops = fields.Integer(string='Drops', compute='_compute_supply_drops', store=True)
    supply_ducts = fields.Integer(string='Ducts', compute='_compute_supply_ducts', store=True)

    room_id = fields.Char(string='Room #')
    length = fields.Float(string='Length (m)')
    width = fields.Float(string='Width (m)')
    area = fields.Float(string='Area (sq m)', compute='_compute_area', store=True)

    @api.depends('length', 'width')
    def _compute_area(self):
        for record in self:
            record.area = record.length * record.width

    @api.depends('room_id')
    def _compute_supply_name(self):
        for record in self:
            record.supply = record.room_id

    @api.depends('area', 'order_id.correct_rate')
    def _compute_supply_trickle2(self):
        for record in self:
            if record.order_id:
                total_area = sum(record.order_id.room_measurement_ids.mapped('area')) or 1
                for line in record.order_id.room_measurement_ids:
                    line.supply_trickle2 = line.order_id.correct_rate * (line.area / total_area)

    @api.depends('area', 'order_id.extract_rate', 'supply_trickle2')
    def _compute_supply_boost2(self):
        for record in self:
            if record.order_id:
                total_area = sum(record.order_id.room_measurement_ids.mapped('area')) or 1
                for line in record.order_id.room_measurement_ids:
                    supply_extract_rate = line.order_id.extract_rate * (line.area / total_area)
                    line.supply_boost2 = max(supply_extract_rate, line.supply_trickle2 * 1.1)

    @api.depends('supply_trickle2')
    def _compute_supply_drops(self):
        for rec in self:
            if rec.supply_trickle2 < 1:
                rec.supply_drops = 0
            elif 1 <= rec.supply_trickle2 <= 12.9:
                rec.supply_drops = 1
            elif 12.9 < rec.supply_trickle2 >= 13:
                rec.supply_drops = 2
            else:
                rec.supply_drops = 0

    @api.depends('supply_trickle2')
    def _compute_supply_ducts(self):
        for rec in self:
            if rec.supply_trickle2 < 1:
                rec.supply_ducts = 0
            elif 1 <= rec.supply_trickle2 <= 12.95:
                rec.supply_ducts = 1
            elif 12.95 < rec.supply_trickle2 <= 12.99:
                rec.supply_ducts = 2
            elif 12.99 < rec.supply_trickle2 >= 13:
                rec.supply_ducts = 4
            else:
                rec.supply_ducts = 0
