/** @odoo-module **/

import { AccountTypeSelection } from "@account/components/account_type_selection/account_type_selection";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

const originalSetup = AccountTypeSelection.prototype.setup;

patch(AccountTypeSelection.prototype, {
    setup(...args) {
        const result = originalSetup.call(this, ...args);
        const viewChoice = this.choices?.find((choice) => choice.value === "view");
        if (!viewChoice) {
            return result;
        }
        const alreadyInAnyGroup = this.groups?.some((group) =>
            (group.choices || []).some((choice) => choice.value === "view")
        );
        if (alreadyInAnyGroup) {
            return result;
        }
        const otherGroup = this.groups?.find(
            (group) => (group.choices || []).some((choice) => choice.value.startsWith("off_balance"))
        );
        if (otherGroup) {
            otherGroup.choices = [...otherGroup.choices, viewChoice];
            return result;
        }
        this.groups = (this.groups || []).slice();
        this.groups.unshift({
            label: _t("Hierarchy"),
            choices: [viewChoice],
            section: "balance_sheet",
        });
        return result;
    },
});

