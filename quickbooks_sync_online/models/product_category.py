# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

from .mapping.qbo_map_product import ODOO_CATEGORY_LABEL

_logger = logging.getLogger(__name__)


class ProductCategory(models.Model):
    _name = 'product.category'
    _inherit = ['product.category', 'qbo.transaction.mixin']

    _qbo_map = 'qbo.map.product'

    qbo_product_categ_ids = fields.One2many(
        comodel_name=_qbo_map,
        inverse_name='category_id',
        string='QBO Products from Category',
        readonly=True,
    )
    qbo_detailed_type = fields.Selection(
        selection=lambda self: self._get_qbo_product_types(),
        string='To QBO Product Type',
        help='The current category will be exported to QBO as a product with this type '
             'in accordance to QBO setting "Sync Products as Category".',
    )

    def update_category_in_qbo(self):
        """Update Product as category to the Intuit company."""
        _logger.info('Update products as categories "%s" to Intuit.' % self.ids)
        self.ensure_one()

        company = self.define_transaction_company()
        company._check_qbo_auth()

        mapping = self.qbo_product_categ_ids\
            .filtered(lambda r: r.company_id == company)

        self._check_requirements(company)
        self._write_info('pending', '', company.id)

        self._update_one_odoo_to_qbo(mapping)

        return mapping

    @api.onchange('qbo_detailed_type')
    def _onchange_qbo_detailed_type(self):

        if not self.qbo_detailed_type:
            return

        mapping = self.qbo_product_categ_ids\
            .filtered(lambda r: r.company_id == self.env.company)

        if not mapping:
            return

        mapping = self.update_category_in_qbo()
        mapping._origin.qbo_object = mapping.qbo_object

        self._origin.qbo_state = self.qbo_state
        self._origin.qbo_transaction_info = self.qbo_transaction_info

    def _get_qbo_product_types(self):
        return [
            ('NonInventory', 'Consumable'),
            ('Service', 'Service'),
            ('Inventory', 'Storable Product'),
        ]

    @staticmethod
    def _get_qbo_unique_identifier():
        return 'Name'

    def _format_duplicate_name(self):
        return 'product', self.name, 'Products'

    def _any_qbo_checking(self, map_type, company):
        self._check_qbo_duplicate(company.id, map_type=map_type)
        return True

    def _get_map_extra_vals(self, map_model):
        return {
            'is_exported': True,
            'category_id': self.id,
        }

    def _get_qbo_mapping(self, map_type, company_id):
        map_instance = self.map_model.search([
            ('company_id', '=', company_id),
            ('qbo_lib_type', '=', map_type),
            ('category_id', '=', self.id),
        ])
        return map_instance

    def _set_qbo_values(self, qbo_lib_model, company, **kw):
        self.ensure_one()

        self = self.with_company(company)

        qbo_lib_model.Type = self.qbo_detailed_type
        qbo_lib_model.Name = self._prepare_qbo_name()
        qbo_lib_model.Description = f'{self.complete_name} {ODOO_CATEGORY_LABEL}'
        qbo_lib_model.PurchaseDesc = self.complete_name or ''

        if self.qbo_detailed_type == 'Inventory':
            qbo_lib_model.QtyOnHand = 0
            qbo_lib_model.TrackQtyOnHand = True
            qbo_lib_model.InvStartDate = str(company.qbo_export_date_point)
            inventory_asset = self.property_stock_valuation_account_id or \
                company.qbo_default_stock_valuation_account_id
            inventory_asset_rel = inventory_asset.get_qbo_related_account(company.id)
            qbo_lib_model.AssetAccountRef = {'value': inventory_asset_rel.qbo_id}

        income_account_rel = self.property_account_income_categ_id\
            .get_qbo_related_account(company.id)
        qbo_lib_model.IncomeAccountRef = {
            'value': income_account_rel.qbo_id,
        }
        expence_account_rel = self.property_account_expense_categ_id\
            .get_qbo_related_account(company.id)
        qbo_lib_model.ExpenseAccountRef = {
            'value': expence_account_rel.qbo_id,
        }

    def _check_requirements(self, company):
        self.ensure_one()
        self = self.with_company(company)

        if not self.qbo_detailed_type:
            raise ValidationError(_(
                'In order to synchronize product cateogories instead of products to QBO, you need'
                'to define "QBO Product Type" field on every product category. So it will be '
                'correctly synchronized to QBO as either Inventory or Non-Inventory types.'
            ))

        if self.qbo_detailed_type == 'Inventory':
            inventory_asset = self.property_stock_valuation_account_id or \
                company.qbo_default_stock_valuation_account_id
            inventory_asset.get_qbo_related_account(company.id)

        income_account = self.property_account_income_categ_id
        income_account.get_qbo_related_account(company.id)

        expence_account = self.property_account_expense_categ_id
        expence_account.get_qbo_related_account(company.id)

    def _make_message_post(self, *args, **kw):  # TODO
        """The 'product.category' model has no mail mixin. So, it's the point to improve."""
        pass
