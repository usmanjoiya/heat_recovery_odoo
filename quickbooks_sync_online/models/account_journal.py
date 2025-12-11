# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import models

from .utils import expected_one


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    _qbo_map = 'qbo.map.payment.method'

    @expected_one
    def get_qbo_related_method(self, company_id):
        qbo_pay_method = self.env[self._qbo_map].search([
            ('journal_id', '=', self.id),
            ('company_id', '=', company_id),
        ], limit=1)
        return qbo_pay_method
