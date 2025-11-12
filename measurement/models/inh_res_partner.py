from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re


class ResPartner(models.Model):
    _inherit = 'res.partner'

    postal_id = fields.Many2one('shipping.cost')
    postal_id_domain = fields.Many2many('postal.code')


    @api.model
    def create(self, vals):
        """Set postal_id automatically on create, based on zip."""
        for val in vals:
            if val.get('zip') and not val.get('postal_id'):
                postal = self.env['shipping.cost']._get_postal_from_zip(val['zip'])
                if postal:
                    val['postal_id'] = postal.id
        return super().create(vals)

    def write(self, vals):
        """Update postal_id automatically when zip changes."""
        res = super().write(vals)
        if 'zip' in vals:
            for partner in self:
                postal = self.env['shipping.cost']._get_postal_from_zip(partner.zip)
                partner.postal_id = postal.id if postal else False
        return res
