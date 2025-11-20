# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging

from odoo import models, fields

from ..utils import QboClass

_logger = logging.getLogger(__name__)

try:
    from quickbooks.objects.term import Term
except (ImportError, IOError) as ex:
    _logger.error(ex)


class QboMapTerm(models.Model):
    _name = 'qbo.map.term'
    _inherit = 'qbo.map.mixin'
    _description = 'Qbo Map Term'

    _qbo_lib_class = QboClass(Term)

    _res_model = 'account.payment.term'
    _map_routes = {
        'qbo_name': ('["Name"]', ''),
    }

    term_id = fields.Many2one(
        comodel_name=_res_model,
        string='ODOO PaymentTerm',
    )

    def try_to_map(self, *args, **kw):
        raise NotImplementedError()
