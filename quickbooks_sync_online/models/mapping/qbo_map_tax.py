# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import json
import logging

from odoo import fields, models
from odoo.osv import expression

from ..utils import QboClass

_logger = logging.getLogger(__name__)

try:
    from quickbooks.objects.taxrate import TaxRate
except (ImportError, IOError) as ex:
    _logger.error(ex)


class QboMapTax(models.Model):
    _name = 'qbo.map.tax'
    _inherit = 'qbo.map.mixin'
    _description = 'Qbo Map Tax'

    _qbo_lib_class = QboClass(TaxRate)

    _res_model = 'account.tax'
    _related_field = 'tax_id'
    _map_routes = {
        'qbo_name': ('["Name"]', ''),
    }
    _odoo_routes = {
        'active': ('["Active"]', True),
        'name': ('["Name"]', ''),
        'amount': ('["RateValue"]', 0.0),
    }

    tax_id = fields.Many2one(
        comodel_name=_res_model,
        string='ODOO Tax',
        domain="[('company_id', '=', company_id)]",
    )

    def _adjust_odoo_values(self, vals):
        res = super(QboMapTax, self)._adjust_odoo_values(vals)
        res['type_tax_use'] = 'sale'  # Currently only customer-based taxes.
        res['company_id'] = self.company_id.id
        res['description'] = '%.2f' % res['amount'] + '%'
        res['price_include'] = False
        res['include_base_amount'] = False
        res['is_base_affected'] = False
        return res

    def _update_odoo_search_domain(self, domain):
        self.ensure_one()
        qbo_object_body = json.loads(self.qbo_object)
        add_domain = [
            ('company_id', '=', self.company_id.id),
            ('type_tax_use', '=', 'sale'),  # Currently only customer-based taxes.
            ('amount', '=', qbo_object_body.get('RateValue', False)),
        ]
        return [expression.AND([domain, add_domain])]

    def get_qbo_related_taxcode(self, search_field, company_id):
        qbo_related_taxcode = self.env['qbo.map.taxcode'].search([
            (search_field, '=', self.qbo_id),
            ('company_id', '=', company_id),
        ], limit=1)
        return qbo_related_taxcode
