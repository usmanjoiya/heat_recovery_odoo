# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging

from odoo import models, fields

from ..utils import QboClass

_logger = logging.getLogger(__name__)

try:
    from quickbooks.objects.taxcode import TaxCode
except (ImportError, IOError) as ex:
    _logger.error(ex)


class QboMapTaxcode(models.Model):
    _name = 'qbo.map.taxcode'
    _inherit = 'qbo.map.mixin'
    _description = 'Qbo Map Taxcode'

    _qbo_lib_class = QboClass(TaxCode)
    _map_routes = {
        'qbo_name': ('["Name"]', ''),
        'sales_tax_rate_id':
            ('["SalesTaxRateList"]["TaxRateDetail"][0]["TaxRateRef"]["value"]', ''),
        'purchase_tax_rate_id':
            ('["PurchaseTaxRateList"]["TaxRateDetail"][0]["TaxRateRef"]["value"]', ''),
    }

    sales_tax_rate_id = fields.Char(
        string='Sales Tax Id',
        default='',
    )
    purchase_tax_rate_id = fields.Char(
        string='Purchase Tax Id',
        default='',
    )

    def try_to_map(self, *args, **kw):
        raise NotImplementedError()
