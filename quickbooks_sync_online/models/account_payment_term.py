# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import models

from .utils import expected_one


class AccountPaymentTerm(models.Model):
    _inherit = 'account.payment.term'

    _qbo_map = 'qbo.map.term'

    @expected_one
    def get_qbo_related_pay_term(self, company_id):
        """Get related map instance."""
        qbo_related_payment = self.env[self._qbo_map].search([
            ('term_id', '=', self.id),
            ('company_id', '=', company_id),
        ])
        return qbo_related_payment
