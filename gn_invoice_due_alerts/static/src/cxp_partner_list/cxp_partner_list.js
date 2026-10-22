/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";

export class CxpPartnerListController extends ListController {
    static template = "gn_invoice_due_alerts.CxpPartnerListView";

    get isGroupedView() {
        return this.model.root.isGrouped;
    }

    get allGroupsExpanded() {
        const root = this.model.root;
        return root.isGrouped && root.groups.every((group) => !group.isFolded);
    }

    async onToggleAllGroups() {
        const root = this.model.root;
        if (!root.isGrouped) {
            return;
        }
        const expand = root.groups.some((group) => group.isFolded);
        for (const group of root.groups) {
            if (expand && group.isFolded) {
                await group.toggle();
            } else if (!expand && !group.isFolded) {
                group.model._updateConfig(group.config, { isFolded: true }, { reload: false });
            }
        }
    }
}

registry.category("views").add("cxp_partner_payable_list", {
    ...listView,
    Controller: CxpPartnerListController,
});
