from odoo import http
from odoo.http import request
from datetime import datetime

from odoo.addons.sale.controllers.product_configurator import SaleProductConfiguratorController

class SaleProductConfiguratorControllerInherit(SaleProductConfiguratorController):

    @http.route('/sale/product_configurator/get_values', type='jsonrpc', auth='user', readonly=True)
    def sale_product_configurator_get_values(
        self,
        product_template_id,
        quantity,
        currency_id,
        so_date,
        product_uom_id=None,
        company_id=None,
        pricelist_id=None,
        ptav_ids=None,
        only_main_product=False,
        **kwargs,
    ):
        """Return all product information needed for the product configurator."""
        if company_id:
            request.update_context(allowed_company_ids=[company_id])

        product_template = self._get_product_template(product_template_id)

        # Build initial combination
        combination = request.env['product.template.attribute.value']
        if ptav_ids:
            combination = request.env['product.template.attribute.value'].browse(ptav_ids).filtered(
                lambda ptav: ptav.product_tmpl_id.id == product_template_id
            )
            unconfigured_ptals = (
                product_template.attribute_line_ids - combination.attribute_line_id
            ).filtered(lambda ptal: ptal.attribute_id.display_type != 'multi')
            combination += unconfigured_ptals.mapped(
                lambda ptal: ptal.product_template_value_ids._only_active()[:1]
            )
        # if not combination:
        #     combination = product_template._get_first_possible_combination()

        currency = request.env['res.currency'].browse(currency_id)
        pricelist = request.env['product.pricelist'].browse(pricelist_id)
        so_date = datetime.fromisoformat(so_date)

        # ✅ Sale Order fields (if so_id provided)
        sale_order_data = {}
        so_id = kwargs.get('so_id')
        if so_id:
            sale_order = request.env['sale.order'].browse(int(so_id))
            if sale_order.exists():
                sale_order_data = {
                    'no_of_manifolds': sale_order.no_of_manifolds,
                    'no_of_points': sale_order.no_of_points,
                }

        # ✅ Apply "No of MANIFOLDS" and "No of Points" to matching attributes if they exist
        updated_combination = combination
        for line in product_template.attribute_line_ids:
            attr_name = line.attribute_id.name

            # Check "No of MANIFOLDS"
            if attr_name == "No of Manifolds" and sale_order_data.get('no_of_manifolds'):
                # find matching value by name or by numeric label
                manifold_val = line.product_template_value_ids.filtered(
                    lambda v: str(v.name).strip() == str(sale_order_data['no_of_manifolds']).strip()
                )
                if manifold_val:
                    updated_combination += manifold_val
                else:
                    # default: first available value
                    updated_combination += line.product_template_value_ids._only_active()[:1]

            # Check "No of Points"
            elif attr_name == "No of Points" and sale_order_data.get('no_of_points'):
                points_val = line.product_template_value_ids.filtered(
                    lambda v: str(v.name).strip() == str(sale_order_data['no_of_points']).strip()
                )
                if points_val:
                    updated_combination += points_val
                else:
                    updated_combination += line.product_template_value_ids._only_active()[:1]

        # ✅ Build response
        result = {
            'products': [
                dict(
                    **self._get_product_information(
                        product_template,
                        updated_combination,
                        currency,
                        pricelist,
                        so_date,
                        quantity=quantity,
                        product_uom_id=product_uom_id,
                        **kwargs,
                    ),
                )
            ],
            'optional_products': [
                dict(
                    **self._get_product_information(
                        optional_product_template,
                        optional_product_template._get_first_possible_combination(
                            parent_combination=updated_combination
                        ),
                        currency,
                        pricelist,
                        so_date,
                        parent_combination=product_template.attribute_line_ids.product_template_value_ids,
                        **kwargs,
                    ),
                    parent_product_tmpl_id=product_template.id,
                )
                for optional_product_template in product_template.optional_product_ids
                if self._should_show_product(optional_product_template, updated_combination)
            ] if not only_main_product else [],
            'currency_id': currency_id,
        }

        # Merge Sale Order fields for JS usage
        result.update(sale_order_data)

        return result

