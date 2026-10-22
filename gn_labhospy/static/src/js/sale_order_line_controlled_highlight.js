/** @odoo-module **/

import { SaleOrderLineListRenderer } from "@sale/js/sale_order_line_field/sale_order_line_field";
import { patch } from "@web/core/utils/patch";

/**
 * Odoo lista decoration-warning -> clase text-warning (poco visible en tabla).
 * Añadimos table-warning en filas con producto controlado (LabHosPy).
 */
patch(SaleOrderLineListRenderer.prototype, {
    getRowClass(record) {
        let classes = super.getRowClass(record);
        if (
            record.data?.gn_labhospy_is_controlled &&
            !record.data?.display_type
        ) {
            classes = `${classes} table-warning`.trim();
        }
        return classes;
    },
});
