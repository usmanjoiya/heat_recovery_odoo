# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging

from odoo import fields, models
from odoo.osv import expression

from ..utils import QboClass

_logger = logging.getLogger(__name__)

try:
    from quickbooks.objects.account import Account
except (ImportError, IOError) as ex:
    _logger.error(ex)


class QboMapAccount(models.Model):
    _name = 'qbo.map.account'
    _inherit = 'qbo.map.mixin'
    _description = 'Qbo Map Account'

    _qbo_lib_class = QboClass(Account)

    _res_model = 'account.account'
    _related_field = 'account_id'
    _map_routes = {
        'qbo_name': ('["Name"]', ''),
        'account_type': ('["AccountType"]', ''),
        'account_sub_type': ('["AccountSubType"]', ''),
        'classification': ('["Classification"]', ''),
    }

    account_type = fields.Char(
        string='Account type',
        readonly=True,
    )
    account_sub_type = fields.Char(
        string='Account subtype',
        readonly=True,
    )
    classification = fields.Char(
        string='Classification',
        readonly=True,
    )
    # account_id = fields.Many2one(
    #     comodel_name='account.account',
    #     string='ODOO Account',
    #     domain="[('company_id', '=', company_id)]",
    # )
    account_id = fields.Many2one(
        comodel_name='account.account',
        string='ODOO Account'
    )

    def _update_odoo_search_domain(self, domain):
        self.ensure_one()
        return [expression.AND([domain, [('company_id', '=', self.company_id.id)]])]
