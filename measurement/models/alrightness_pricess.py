from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re



class AlrightnessPricess(models.Model):
    _name = "alrightness.pricess"
    _description = 'Alrightness Pricess'


    name = fields.Char(string="Name")

    area = fields.Float(string="Area 1 (m²)")
    area2 = fields.Float(string="Area 2 (m²)")
    area3 = fields.Float(string="Area 3 (m²)")
    area4 = fields.Float(string="Area 4 (m²)")

    guide_price_1 = fields.Float(string="Guide Price 1")
    guide_price_2 = fields.Float(string="Guide Price 2")
    guide_price_3 = fields.Float(string="Guide Price 3")
    guide_price_4 = fields.Float(string="Guide Price 4")


    @api.onchange('guide_price_1')
    def _change_guide_price(self):
        for x in self:
            x.guide_price_2 = x.guide_price_1 * 2
            x.guide_price_3 = x.guide_price_1 * 3
            x.guide_price_4 = x.guide_price_1 * 4
