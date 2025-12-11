# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging

from odoo import models, fields
from odoo.exceptions import ValidationError


_logger = logging.getLogger(__name__)


class StockWarehouse(models.Model):
    _name = 'stock.warehouse'
    _inherit = ['stock.warehouse', 'qbo.transaction.mixin']

    _qbo_map = 'qbo.map.department'

    qbo_department_ids = fields.One2many(
        comodel_name=_qbo_map,
        inverse_name='warehouse_id',
        string='QBO Department',
        readonly=True,
    )

    def _set_qbo_values(self, qbo_lib_model, company, **kw):
        self.ensure_one()

        qbo_lib_model.Active = self.active
        qbo_lib_model.Name = self._prepare_qbo_name()

    def check_and_perform_export(self, company, map_type):
        _logger.info('Check and perform export of warehouses "%s".' % self.ids)
        raise_exception = self.env.context.get('raise_exception')

        def _do_raise(info):
            if raise_exception:
                raise ValidationError(info)

        for warehouse in self.with_context(company_id=company.id):
            try:
                if warehouse._get_map_instance_or_raise(
                        map_type, company.id, raise_if_not_found=False):
                    warehouse._write_info('proxy', '', company.id)
                    continue
            except ValidationError as ex:
                _do_raise(ex.args[0])
                warehouse._write_info('rejected', ex.args[0], company.id)
                continue

            warehouse._write_info('pending', '', company.id)

            job_kwargs = warehouse._get_transaction_job_kwargs()
            warehouse._mark_failed_jobs_as_cancel(identity_key=job_kwargs['identity_key'])

            warehouse.with_delay(**job_kwargs)._export_qbo_one(map_type, company)

    def export_warehouse_to_qbo(self):
        """Export Departments to Intuit company. Call from UI."""
        _logger.info('Export Departments "%s" to Intuit.' % self.ids)
        company = self.define_transaction_company()
        company._check_qbo_auth()

        records = self.filtered(lambda x: not x.qbo_department_ids and x.company_id == company)
        if not records:
            _logger.info('There are no warehouses for export.')
            return False

        return records.with_context(raise_exception=True).check_and_perform_export(company, self.map_type)

    def update_warehouse_in_qbo(self):
        """Update Warehouse to Intuit company."""
        _logger.info('Update warehouses "%s" to Intuit.' % self.ids)

        company = self.define_transaction_company()
        company._check_qbo_auth()
        map_type = self.map_type

        for rec in self.with_context(company_id=company.id):
            mapping = rec._get_map_instance_or_raise(map_type, company.id)
            rec._write_info('pending', '', company.id)

            job_kwargs = rec._get_transaction_job_kwargs()
            rec.with_delay(**job_kwargs)._update_one_odoo_to_qbo(mapping)
