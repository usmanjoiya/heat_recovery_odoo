# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging

from odoo import models, fields, api


_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    qbo_product_ids = fields.One2many(
        comodel_name='qbo.map.product',
        compute='_compute_qbo_fields',
    )
    qbo_transaction_info = fields.Text(
        compute='_compute_qbo_fields',
    )
    qbo_transaction_date = fields.Datetime(
        compute='_compute_qbo_fields',
    )
    qbo_state = fields.Selection(
        selection=[
            ('todo', 'ToDo'),
            ('rejected', 'Rejected'),
            ('pending', 'Pending'),
            ('failed', 'Failed'),
            ('proxy', 'Done'),
        ],
        compute='_compute_qbo_fields',
    )

    @api.depends('product_variant_ids')
    def _compute_qbo_fields(self):
        company = self.env.company

        for rec in self:
            product_ids = transact_info = transact_date = qbo_state = False

            if len(rec.product_variant_ids) == 1:
                product = rec.product_variant_id.with_company(company)

                product_ids = product.qbo_product_ids
                transact_info = product.qbo_transaction_info
                transact_date = product.qbo_transaction_date
                qbo_state = product.qbo_state

            rec.update({
                'qbo_product_ids': product_ids,
                'qbo_transaction_info': transact_info,
                'qbo_transaction_date': transact_date,
                'qbo_state': qbo_state,
            })

    def export_product_to_qbo_tmpl(self):
        """Export Products Tempalted to the Intuit company. Call from UI."""
        _logger.info('Export Product Templates "%s" to Intuit.' % self.ids)
        return self.mapped('product_variant_ids').export_product_to_qbo()

    def update_product_in_qbo_tmpl(self):
        """Update Product Templates to the Intuit company."""
        _logger.info('Update Product Templates "%s" to Intuit.' % self.ids)
        return self.mapped('product_variant_ids').update_product_in_qbo()
