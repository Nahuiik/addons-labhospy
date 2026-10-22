/** @odoo-module **/

import { Component, useState, onWillUpdateProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary } from "@web/views/fields/formatters";
import { PurchaseChartPanel } from "./chart_panel";
import { buildRadarOption } from "./echarts_utils";

const MODEL = "purchase.dashboard.service";

export class PurchaseEntitySidePanel extends Component {
    static template = "gn_purchase_dashboard.EntitySidePanel";
    static components = { PurchaseChartPanel };
    static props = {
        open: Boolean,
        entityType: { type: String, optional: true },
        entityId: { type: Number, optional: true },
        filters: Object,
        currencyId: Number,
        darkMode: Boolean,
        onClose: Function,
        onDrilldown: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ loading: false, data: null });
        onWillUpdateProps(async (nextProps) => {
            if (nextProps.open && nextProps.entityId && nextProps.entityId !== this.props.entityId) {
                await this.load(nextProps);
            }
        });
        this.load();
    }

    async load(props = this.props) {
        if (!props.open || !props.entityId) return;
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(MODEL, "get_entity_panel", [
                props.filters,
                props.entityType || "vendor",
                props.entityId,
            ]);
        } finally {
            this.state.loading = false;
        }
    }

    radarOptionBuilder = (config, darkMode) => buildRadarOption(this.state.data?.scorecard?.dimensions || [], darkMode);

    fmtValue(kpi) {
        const v = kpi.value || 0;
        if (kpi.format === "currency") return formatMonetary(v, { currencyId: this.props.currencyId });
        if (kpi.format === "days") return `${Number(v).toFixed(1)} d`;
        return Number(v).toLocaleString();
    }

    onCloseClick() {
        if (this.props.onClose) this.props.onClose();
    }

    onDocClick(doc, type) {
        if (this.props.onDrilldown) this.props.onDrilldown(type, doc.id);
    }
}
