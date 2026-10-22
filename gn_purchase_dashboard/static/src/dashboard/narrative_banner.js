/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

const PREVIEW_LEN = 140;

export class PurchaseNarrativeBanner extends Component {
    static template = "gn_purchase_dashboard.NarrativeBanner";
    static props = {
        narrative: { type: String, optional: true },
        loading: Boolean,
    };

    setup() {
        this.state = useState({ expanded: false });
    }

    get hasNarrative() {
        return Boolean(this.props.narrative?.trim());
    }

    get showToggle() {
        return (this.props.narrative?.length || 0) > PREVIEW_LEN;
    }

    get displayText() {
        const text = this.props.narrative || "";
        if (this.state.expanded || text.length <= PREVIEW_LEN) return text;
        return `${text.slice(0, PREVIEW_LEN).trim()}…`;
    }

    get toggleLabel() {
        return this.state.expanded ? _t("Ver menos") : _t("Ver más");
    }

    toggleExpand(ev) {
        ev?.stopPropagation();
        this.state.expanded = !this.state.expanded;
    }
}
