# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging

from odoo import models, fields

from ..utils import QboClass

_logger = logging.getLogger(__name__)

try:
    from quickbooks.objects.paymentmethod import PaymentMethod
except (ImportError, IOError) as ex:
    _logger.error(ex)


class QboMapPaymentMethod(models.Model):
    _name = 'qbo.map.payment.method'
    _inherit = 'qbo.map.mixin'
    _description = 'Qbo Map Payment Method'
    _order = 'sequence'

    _qbo_lib_class = QboClass(PaymentMethod)

    _map_routes = {
        'qbo_name': ('["Name"]', ''),
        'method_type': ('["Type"]', ''),
    }

    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    method_type = fields.Char(
        string='Type',
    )
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='ODOO Journal',
    )

    def try_to_map(self, *args, **kw):
        raise NotImplementedError()
