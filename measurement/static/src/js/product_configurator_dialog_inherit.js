/** @odoo-module **/

import { ProductConfiguratorDialog } from "@sale/js/product_configurator_dialog/product_configurator_dialog";
import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";


patch(ProductConfiguratorDialog, {
    // 👇 extend static props definition
    props: {
        ...ProductConfiguratorDialog.props,
        SaleID: { type: Number, optional: true },
    },
});


patch(ProductConfiguratorDialog.prototype, {

    async _loadData(onlyMainProduct) {
        console.log('📌 _loadData called with onlyMainProduct:', onlyMainProduct);
        debugger;

            const result = await rpc(this.getValuesUrl, {
            product_template_id: this.props.productTemplateId,
            quantity: this.props.quantity,
            currency_id: this.currency.id,
            so_date: this.props.soDate,

            so_id: this.props.SaleID,
            product_uom_id: this.props.productUOMId,
            company_id: this.props.companyId,
            pricelist_id: this.props.pricelistId,
            ptav_ids: this.props.ptavIds,
            only_main_product: onlyMainProduct,
            show_packaging: this.env.showPackaging,
            ...this._getAdditionalRpcParams(),
        });
        console.log('🔍 product_template:', result.product_template);
        console.log('🔍 product_template keys:', Object.keys(result.product_template || {}));
        console.log('✅ Modified RPC data:', result);
        return result;
    }

});



