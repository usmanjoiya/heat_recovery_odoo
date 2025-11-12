from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re


class ShippingCost(models.Model):
    _name = 'shipping.cost'
    _description = 'Shipping Cost'

    name = fields.Char(string='Postal code')
    cost = fields.Float(string='Cost')
    country_id = fields.Many2one('res.country', string="Country")

    @api.model
    def _get_postal_from_zip(self, zip_code):
        """Find matching shipping.cost record by checking prefixes of zip (5→4→3→2)."""
        if not zip_code:
            return False
        zip_code = zip_code.strip().upper()
        ShippingCost = self.env['shipping.cost']
        for length in [5, 4, 3, 2]:
            prefix = zip_code[:length]
            postal = ShippingCost.search([('name', '=', prefix)], limit=1)
            if postal:
                return postal
        return False



