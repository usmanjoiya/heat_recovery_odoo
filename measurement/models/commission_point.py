from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re


class CommissionPoint(models.Model):
    _name = 'commission.point'
    _description = 'DWELLING RATES MVHR'


    name = fields.Char(string='name', readonly=True,compute='_compute_name', store=True)
    extract = fields.Char(string='Extract')
    high = fields.Float(string='High L/S')

    @api.depends('extract', 'high')
    def _compute_name(self):
        for rec in self:
            if rec.extract and rec.high:
                rec.name = f"{rec.extract} - {rec.high}"
            elif rec.extract:
                rec.name = rec.extract
            else:
                rec.name = "Unnamed"
