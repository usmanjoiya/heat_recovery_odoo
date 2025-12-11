# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging

from odoo import fields, models
from odoo.osv import expression

from .mapping.qbo_map_product import OPTIONS_PATTERN


_logger = logging.getLogger(__name__)

SERVICE = 'service'
STORABLE = 'product'
CONSUMABLE = 'consu'


class ProductProduct(models.Model):
    _name = 'product.product'
    _inherit = ['product.product', 'qbo.transaction.mixin']

    _qbo_map = 'qbo.map.product'

    qbo_product_ids = fields.One2many(
        comodel_name=_qbo_map,
        inverse_name='product_id',
        string='QBO Products',
        readonly=True,
    )

    def export_product_to_qbo(self):
        """Export Products to the Intuit company. Call from UI."""
        _logger.info('Export Products "%s" to Intuit.' % self.ids)
        company = self.define_transaction_company()
        company._check_qbo_auth()
        company._check_qbo_product_settings()

        export_dict, __ = self.with_context(raise_exception=True)\
            ._collect_qbo_export_dict(self.map_types, company)

        return company._process_qbo_export_dict(export_dict)

    def update_product_in_qbo(self):
        """Update Product to the Intuit company."""
        _logger.info('Update products "%s" to Intuit.' % self.ids)
        company = self.define_transaction_company()
        company._check_qbo_auth()
        company._check_qbo_product_settings()
        map_type = self.map_type

        for product in self.with_context(company_id=company.id):
            mapping = product._get_map_instance_or_raise(map_type, company.id)
            product._check_requirements(company)
            product._write_info('pending', '', company.id)

            job_kwargs = product._get_transaction_job_kwargs(map_type)
            job_kwargs['description'] = (
                f'Update {product._description} "{product.display_name}" to QBO'
            )
            product._mark_failed_jobs_as_cancel(identity_key=job_kwargs['identity_key'])

            product.with_delay(**job_kwargs)._update_one_odoo_to_qbo(mapping)

    @staticmethod
    def _get_qbo_unique_identifier():
        return 'Name'

    def _update_qbo_search_domain(self, domain, map_type):
        self.ensure_one()

        if self.default_code:
            additional_prefix = [('stock_keeping_unit', '=', self.default_code)]
        else:
            additional_prefix = [('stock_keeping_unit', 'in', (False, ''))]

        if self.product_template_attribute_value_ids:
            combination_name = self.product_template_attribute_value_ids._get_combination_name()
            additional_postfix = [('variant_options', '=', combination_name)]
        else:
            additional_postfix = [('variant_options', 'in', (False, ''))]

        return expression.AND([domain, additional_prefix, additional_postfix])

    def _format_duplicate_name(self):
        return 'product', self.name, 'Products'

    def _check_qbo_duplicate(self, *args, **kw):
        kw['alias'] = 'Product'
        return super(ProductProduct, self)._check_qbo_duplicate(*args, **kw)

    def _any_qbo_checking(self, map_type, company):
        self._check_qbo_duplicate(company.id, map_type=map_type)
        return True

    def _prepare_qbo_name(self, *args, **kw):
        self.ensure_one()
        return self.display_name

    def _prepare_qbo_description(self):
        description = self.description_sale or ''

        if not self.product_template_attribute_value_ids:
            return description

        combination_name = self.product_template_attribute_value_ids._get_combination_name()
        postfix = OPTIONS_PATTERN % combination_name

        if description:
            return f'{description} {postfix}'

        return f'{self.name} {postfix}'

    def _get_product_type_from_settings(self, company):
        product_type = self.type
        as_consumable = company.qbo_sync_storable_to_consumable

        if as_consumable and product_type == STORABLE:
            product_type = CONSUMABLE

        return product_type

    def _set_qbo_values(self, qbo_lib_model, company, **kw):
        self.ensure_one()

        self = self.with_company(company)

        qbo_lib_model.Active = self.active
        qbo_lib_model.Name = self._prepare_qbo_name()
        qbo_lib_model.Description = self._prepare_qbo_description()
        qbo_lib_model.PurchaseDesc = self.description_purchase or ''
        qbo_lib_model.Sku = self.default_code or ''
        qbo_lib_model.UnitPrice = self.list_price
        qbo_lib_model.PurchaseCost = self.standard_price
        qbo_lib_model.Taxable = bool(self.taxes_id)

        product_type = self._get_product_type_from_settings(company)

        if product_type == SERVICE:
            qbo_lib_model.Type = 'Service'
        elif product_type == STORABLE:
            qbo_lib_model.Type = 'Inventory'
            qbo_lib_model.QtyOnHand = self.qty_available
            qbo_lib_model.TrackQtyOnHand = True
            qbo_lib_model.InvStartDate = str(company.qbo_export_date_point)
            inventory_asset = self.categ_id.property_stock_valuation_account_id or \
                company.qbo_default_stock_valuation_account_id
            inventory_asset_rel = inventory_asset.get_qbo_related_account(company.id)
            qbo_lib_model.AssetAccountRef = {'value': inventory_asset_rel.qbo_id}
        else:
            qbo_lib_model.Type = 'NonInventory'

        income_account = self.property_account_income_id or \
            self.categ_id.property_account_income_categ_id
        income_account_rel = income_account.get_qbo_related_account(company.id)
        qbo_lib_model.IncomeAccountRef = {'value': income_account_rel.qbo_id}

        expence_account = self.property_account_expense_id or \
            self.categ_id.property_account_expense_categ_id
        expence_account_rel = expence_account.get_qbo_related_account(company.id)
        qbo_lib_model.ExpenseAccountRef = {'value': expence_account_rel.qbo_id}

    def _check_requirements(self, company):
        self.ensure_one()
        self = self.with_company(company)

        income_account = self.property_account_income_id or \
            self.categ_id.property_account_income_categ_id
        income_account.get_qbo_related_account(company.id)

        expence_account = self.property_account_expense_id or \
            self.categ_id.property_account_expense_categ_id
        expence_account.get_qbo_related_account(company.id)

        product_type = self._get_product_type_from_settings(company)

        if product_type == STORABLE:
            inventory_asset = self.categ_id.property_stock_valuation_account_id or \
                company.qbo_default_stock_valuation_account_id
            inventory_asset.get_qbo_related_account(company.id)

    def _export_qbo_batch(self, map_type, company, ctx_params):
        _logger.info('Export to QBO "%s". Create jobs.' % str(self))

        for rec in self:
            rec._write_info('pending', '', company.id)

        job_kwargs = self[:1]._get_transaction_job_kwargs(map_type)

        if len(self) == 1:
            self._mark_failed_jobs_as_cancel(identity_key=job_kwargs['identity_key'])

            return self.with_context(company_id=company.id)\
                .with_delay(**job_kwargs)\
                ._export_qbo_one(map_type, company)

        job_kwargs.update(
            description=f'Export {self._description} (batch) to QBO',
            identity_key=f'qbo_export_{map_type}_{self}',

        )
        self._mark_failed_jobs_as_cancel(identity_key=job_kwargs['identity_key'])

        return self.with_context(company_id=company.id)\
            .with_delay(**job_kwargs)\
            ._perform_export_qbo_batch(map_type, company)

    def to_qbo_json(self):
        self.ensure_one()

        company = self.define_transaction_company()

        qbo_lib_model = self._init_qbo_lib_class('item')
        self._set_qbo_values(qbo_lib_model, company)

        return self._display_qbo_json(
            f'DEBUG: {self.name} [{qbo_lib_model.qbo_object_name}]',
            qbo_lib_model.to_dict(),
        )
