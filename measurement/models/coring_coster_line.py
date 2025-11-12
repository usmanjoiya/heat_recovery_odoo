from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re



class CoringCosterLine(models.Model):
    _name = 'coring.coster.line'
    _description = 'Coring Coster'

    order_id = fields.Many2one('sale.order', string='Sale Order', ondelete='cascade')
    core_size = fields.Many2one('coring.coster', string="Core Size")
    amount = fields.Float(string="Amount")
    cost = fields.Float(string="Cost")
    sub_total = fields.Integer(string="Sub Total",compute="_compute_sub_total", store=True)
    total_cost = fields.Integer(string="Total", compute="_compute_total", store=True)


    @api.onchange('core_size')
    def _get_cost(self):
        for core in self:
            if core.core_size:
                core.cost = core.core_size.cost

    @api.depends('amount')
    def _compute_sub_total(self):
        for core in self:
            if core.amount:
                core.sub_total = core.amount * core.cost

    @api.depends('order_id.coring_coster_line_ids.sub_total')
    def _compute_total(self):
        for core in self:
            if core.order_id:
                core.total_cost = sum(core.order_id.coring_coster_line_ids.mapped('sub_total'))
            else:
                core.total_cost = 0.0
