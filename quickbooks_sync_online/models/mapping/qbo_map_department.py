# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging

from odoo import models, fields

from ..utils import QboClass

_logger = logging.getLogger(__name__)

try:
    from quickbooks.objects.department import Department
except (ImportError, IOError) as ex:
    _logger.error(ex)


class QboMapDepartment(models.Model):
    _name = 'qbo.map.department'
    _inherit = 'qbo.map.mixin'
    _description = 'Qbo Map Department'

    _qbo_lib_class = QboClass(Department)

    _res_model = 'stock.warehouse'
    _related_field = 'warehouse_id'
    _reverse_field = 'qbo_department_ids'
    _map_routes = {
        'qbo_name': ('["Name"]', ''),
    }

    warehouse_id = fields.Many2one(
        comodel_name=_res_model,
        string='ODOO Warehouse',
    )
    is_sub_department = fields.Boolean(
        string='Is Sub Department',
    )

    def try_to_map(self, *args, **kw):
        raise NotImplementedError()
