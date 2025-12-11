# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging

from odoo import fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError, ValidationError

from .utils import IntuitResponse, TAXABLE, NON_TAXABLE


_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _create_qbo_so_line(self):
        self.ensure_one()
        search_field = self.order_id._get_sale_item_line_detail()
        company = self.order_id.company_id

        if company.intuit_is_us_company():
            taxcode_value = TAXABLE if self.product_id.taxes_id else NON_TAXABLE
        else:  # It doesn't matter. Currently the feature only for the US Intuit companies.
            taxcode_value = str()
            if self.product_id.taxes_id:  # TODO: we are using slice on 'taxes_id'
                qbo_rel_tax = self.product_id.taxes_id[:1].get_qbo_related_tax(company.id)
                taxcode_value = qbo_rel_tax.get_qbo_related_taxcode(search_field, company.id).qbo_id

        export_line = {
            'Description': self.name,
            'Amount': self.price_subtotal,
            'DetailType': 'SalesItemLineDetail',
            'SalesItemLineDetail': {
                'Qty': self.product_uom_qty,
                'TaxCodeRef': {
                    'value': taxcode_value,
                },
            },
        }

        if not company.qbo_sync_product:
            return export_line

        if company.qbo_sync_product_category:
            qbo_product = self.product_id.categ_id.qbo_product_categ_ids
        else:
            qbo_product = self.product_id.qbo_product_ids

        qbo_product = qbo_product.filtered(lambda r: r.company_id == company)

        export_line['SalesItemLineDetail']['ItemRef'] = {
            'name': qbo_product.qbo_name,
            'value': qbo_product.qbo_id,
        }
        return export_line


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'qbo.transaction.mixin']

    _qbo_map = 'qbo.map.sale.order'

    qbo_sale_ids = fields.One2many(
        comodel_name=_qbo_map,
        inverse_name='order_id',
        string='QBO Sale Order',
        readonly=True,
    )

    def get_qbo_taxes_from_salereceipt(self):
        """Get taxes from Intuit."""
        self.ensure_one()
        company = self.company_id

        company._check_qbo_auth()
        company._check_qbo_tax_settings()
        self._check_requirements(company)

        MapTax = self.env['qbo.map.tax']
        for map_type in MapTax.qbo_map_list():  # TODO: it's not very efficient, but reliable
            MapTax._get_data_from_qbo(company, map_type)

        export_dict, allowed_ids = self.with_context(raise_exception=True)\
            ._collect_qbo_export_dict(self.map_types, company)

        if self.id not in allowed_ids:
            company._process_qbo_export_dict(export_dict)
            return False

        company.with_context(qbo_plain_export=True)._process_qbo_export_dict(export_dict)

        return self._get_qbo_taxes_from_salereceipt()

    @staticmethod
    def _get_sale_item_line_detail():
        return 'sales_tax_rate_id'

    def _set_qbo_values(self, qbo_lib_model, company, **kw):
        self.ensure_one()

        qbo_partner = self.partner_id._get_qbo_mapping('customer', company.id)

        qbo_lib_model.DocNumber = self._prepare_qbo_name()
        qbo_lib_model.CustomerRef = {'value': qbo_partner.qbo_id}
        qbo_lib_model.CurrencyRef = {'value': self.partner_id.currency_id.name}
        qbo_lib_model.Line = [
            line._create_qbo_so_line() for line in self.order_line.filtered('product_id')
        ]

    def _get_products_to_qbo_export(self, company):
        products = self.env['product.product']

        if company.qbo_sync_product_category:
            products = self.mapped('order_line.product_id.categ_id')
        elif company.qbo_sync_product:
            products = self.mapped('order_line.product_id')

        return products

    def _check_requirements(self, company):
        # Check US company
        company.ensure_qbo_us_company()

        # Check state
        if self.state != 'draft':
            raise UserError(_(
                'The Sale Order should be in the "Draft" state.'
            ))

        # Check products
        products = self._get_products_to_qbo_export(company)
        if not products:
            raise UserError(_(
                'You need to add products to the Sale Order "%s".' % self.display_name
            ))

    def _collect_qbo_export_dict(self, map_types, company):
        _logger.info('Collect invoices export dict "%s".' % self.ids)
        self.ensure_one()

        assert len(map_types) == 1

        error_list, allowed_ids = [], []
        raise_exception = self.env.context.get('raise_exception')
        ctx = {'raise_exception': raise_exception}

        # Check products
        products = self._get_products_to_qbo_export(company)
        export_dict, allowed_product_ids = products.with_context(**ctx)\
            ._collect_qbo_export_dict(products.map_types, company)

        for product in products:
            if product.id not in allowed_product_ids:
                alias = products._name.split('.')[-1]
                error_list.append(
                    _('- The %s "%s" needs fixing.' % (alias, product.display_name))
                )

        # Check partner
        partner = self.partner_id
        partner_types_to_export, error_message = partner.with_context(**ctx)\
            ._validate_qbo_type_export('customer', company)

        for map_type in partner_types_to_export:
            export_dict['res.partner'][map_type].append(partner)

        if error_message:
            error_list.append(
                _('- The partner "%s" needs fixing:\n\t- %s' % (partner.name, error_message))
            )

        if error_list:
            info = '\n\n'.join(error_list)
            self._write_info('rejected', info, company.id)
        else:
            allowed_ids.append(self.id)

        return export_dict, allowed_ids

    def _export_qbo_one(self, map_type, company):
        self.ensure_one()

        qbo_lib_model = self._init_qbo_lib_class(map_type)
        self._set_qbo_values(qbo_lib_model, company)

        return self._perform_export_qbo_one(qbo_lib_model, company)

    def _apply_taxes_from_intuit(self, mapping):
        self.ensure_one()

        for tax in mapping.qbo_tax_ids.filtered(lambda r: not r.tax_id):
            tax.with_user(SUPERUSER_ID).try_to_map(summary=False)

        if not mapping:  # It means the customer is tax exempt.
            self.order_line.filtered('product_id').write({
                'tax_id': [(6, 0, [])],
            })

        array = zip(
            self.order_line.filtered('product_id'),
            mapping.order_map_line_ids,
        )

        vals_list = list()
        for so_line, map_line in array:
            taxes = [(6, 0, map_line.tax_map_ids.mapped('tax_id').ids)]
            vals_list.append(
                (1, so_line.id, {'tax_id': taxes}),
            )

        self.write({
            'order_line': vals_list,
        })
        return mapping.qbo_tax_ids.mapped('tax_id')

    def _get_qbo_taxes_from_salereceipt(self):
        company = self.company_id
        mapping = self.map_model

        try:
            self.partner_id._get_map_instance_or_raise('customer', company.id)
        except ValidationError as ex:
            raise ValidationError(_(
                'There were some problems with the export of a customer to QBO. '
                'Read it in the greater details on the customer\'s form view.'
            ))

        if self.partner_id._is_intuit_taxable_customer(company.id):
            mapping, code = self._export_qbo_one(self.map_type, company)

            if not IntuitResponse.is_ok(code):
                raise ValidationError(mapping)

            result, code_ = mapping._delete_qbo_by_id(company)
            if not IntuitResponse.is_ok(code_):
                raise UserError(result)
        else:
            info = 'Customer %s is tax exempt.' % self.partner_id.name
            self._write_info('proxy', info, company.id)

        return self._apply_taxes_from_intuit(mapping)
