/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { SaleOrderLineProductField } from "@sale/js/sale_product_field";
import { ProductConfiguratorDialog } from "@sale/js/product_configurator_dialog/product_configurator_dialog";
import {
    ProductLabelSectionAndNoteField,
    productLabelSectionAndNoteField,
} from "@account/components/product_label_section_and_note_field/product_label_section_and_note_field";
import { useEffect } from "@odoo/owl";
import { serializeDateTime } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { x2ManyCommands } from "@web/core/orm_service";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { uuid } from "@web/core/utils/strings";
import { ComboConfiguratorDialog } from "@sale/js/combo_configurator_dialog/combo_configurator_dialog";
import { ProductCombo } from "@sale/js/models/product_combo";
import { getLinkedSaleOrderLines, serializeComboItem, getSelectedCustomPtav } from "@sale/js/sale_utils";


patch(SaleOrderLineProductField.prototype, {

    async _openProductConfigurator(edit = false, selectedComboItems = []) {
        const saleOrderRecord = this.props.record.model.root;
        const saleOrderLine = this.props.record.data;
        const ptavIds = this._getVariantPtavIds(saleOrderLine);
        let customPtavs = [];

        if (edit) {
            /**
             * no_variant and custom attribute don't need to be given to the configurator for new
             * products.
             */
            ptavIds.push(...this._getNoVariantPtavIds(saleOrderLine));
            customPtavs = await this._getCustomPtavs(saleOrderLine);
        }
        debugger;
        this.dialog.add(ProductConfiguratorDialog, {
            productTemplateId: saleOrderLine.product_template_id.id,
            ptavIds: ptavIds,
            customPtavs: customPtavs,
            quantity: saleOrderLine.product_uom_qty,
            productUOMId: saleOrderLine.product_uom_id.id,
            SaleID: saleOrderLine.order_id.id,
            companyId: saleOrderRecord.data.company_id.id,
            pricelistId: saleOrderRecord.data.pricelist_id.id,
            currencyId: saleOrderLine.currency_id.id,
            soDate: serializeDateTime(saleOrderRecord.data.date_order),
            selectedComboItems: selectedComboItems,
            edit: edit,
            save: async (mainProduct, optionalProducts) => {
                await Promise.all([
                    // Don't add main product if it's a combo product as it has already been added
                    // from combo configurator
                    ...(
                        !selectedComboItems.length ?
                            [applyProduct(this.props.record, mainProduct)]: []
                    ),
                    ...optionalProducts.map(async product => {
                        const line = await saleOrderRecord.data.order_line.addNewRecord({
                            position: 'bottom', mode: 'readonly'
                        });
                        await applyProduct(line, product);
                    }),
                ]);
                this._onProductUpdate();
                saleOrderRecord.data.order_line.leaveEditMode();
            },
            discard: () => {
                if (!selectedComboItems.length) {
                    // Don't delete the main product if it's a combo product as it has been added
                    // from combo configurator
                    saleOrderRecord.data.order_line.delete(this.props.record);
                }
            },
            ...this._getAdditionalDialogProps(),
        });
    }
});
