# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import models

from .utils import expected_one


class AccountAccount(models.Model):
    _inherit = 'account.account'

    _qbo_map = 'qbo.map.account'

    @expected_one
    def get_qbo_related_account(self, company_id):
        qbo_related_account = self.env[self._qbo_map].search([
            ('account_id', '=', self.id),
            ('company_id', '=', company_id),
        ])
        return qbo_related_account

    def _get_qbo_mapping(self, *args, **kw):
        """It's just a code stub for the 'try_to_map()' method."""
        return False
