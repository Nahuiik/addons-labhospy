/** @odoo-module **/

import { Component } from "@odoo/owl";

const AGING_ORDER = ["b0_30", "b31_60", "b61_90", "b90_plus"];

export class CxcPartnerListBanner extends Component {
    static template = "gn_customer_due_alerts.CxcPartnerListBanner";
    static props = {
        state: Object,
        onReload: { type: Function, optional: true },
        isGroupedView: { type: Boolean, optional: true },
        allGroupsExpanded: { type: Boolean, optional: true },
        onToggleGroups: { type: Function, optional: true },
    };

    get agingOrder() {
        return AGING_ORDER;
    }

    onReloadClick() {
        this.props.onReload?.();
    }

    onToggleGroupsClick() {
        this.props.onToggleGroups?.();
    }
}
