# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import models

from .utils import expected_one


class AccountTax(models.Model):
    _inherit = 'account.tax'

    _qbo_map = 'qbo.map.tax'

    @expected_one
    def get_qbo_related_tax(self, company_id):
        """Get related map instance."""
        return self._get_qbo_mapping('taxrate', company_id)

    def _get_qbo_mapping(self, map_type, company_id):
        """Uses in the 'try_to_map()' method."""
        qbo_related_tax = self.env[self._qbo_map].search([
            ('tax_id', '=', self.id),
            ('company_id', '=', company_id),
        ])
        return qbo_related_tax
