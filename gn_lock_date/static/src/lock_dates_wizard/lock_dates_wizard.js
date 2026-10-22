/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { debounce } from "@web/core/utils/timing";

export class LockDatesWizardFormController extends FormController {
    setup() {
        super.setup();
        if (this.props.resModel !== "account.change.lock.date") {
            return;
        }
        this.notification = useService("notification");
        const warn = debounce(() => this._softValidateLockWizard(), 400);
        useBus(this.model.bus, "update", warn);
    }

    _softValidateLockWizard() {
        const root = this.model.root;
        if (!root || root.resModel !== "account.change.lock.date") {
            return;
        }
        const d = root.data;
        const fiscal = d.fiscalyear_lock_date;
        const sale = d.sale_lock_date;
        const purchase = d.purchase_lock_date;
        const tax = d.tax_lock_date;
        const warnings = [];
        if (fiscal && sale && sale > fiscal) {
            warnings.push(_t("Sales lock date is after the global lock date (unusual)."));
        }
        if (fiscal && purchase && purchase > fiscal) {
            warnings.push(_t("Purchase lock date is after the global lock date (unusual)."));
        }
        if (fiscal && tax && tax > fiscal) {
            warnings.push(_t("Tax lock date is after the global lock date (unusual)."));
        }
        if (warnings.length) {
            this.notification.add(warnings.join(" "), { type: "warning", sticky: false });
        }
    }
}

export const lockDatesWizardFormView = {
    ...formView,
    Controller: LockDatesWizardFormController,
};

registry.category("views").add("lock_dates_wizard_form", lockDatesWizardFormView);
