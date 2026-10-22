/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { X2ManyField } from "@web/views/fields/x2many/x2many_field";

/**
 * En el formulario de hr.payslip.run, al abrir un recibo desde la lista O2M se debe
 * navegar al formulario completo de hr.payslip (ventana actual), como en Payroll Enterprise,
 * no al diálogo modal por defecto del x2many.
 */
patch(X2ManyField.prototype, {
    async openRecord(record, options = {}) {
        if (
            this.props?.record?.resModel === "hr.payslip.run" &&
            this.props?.name === "slip_ids" &&
            record &&
            !record.isNew &&
            this.list?.resModel === "hr.payslip"
        ) {
            return this.switchToForm(record, options);
        }
        return super.openRecord(...arguments);
    },
});
