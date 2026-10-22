/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { SalesEmptyState } from "./empty_state";

export class SalesGoalTrackerCard extends Component {
    static template = "gn_sales_dashboard.SalesGoalTrackerCard";
    static components = { SalesEmptyState };
    static props = {
        goal: { type: Object, optional: true },
        closingForecast: { type: Object, optional: true },
        loading: { type: Boolean, optional: true },
        fmtMoney: Function,
        onConfigure: { type: Function, optional: true },
        canConfigure: { type: Boolean, optional: true },
    };

    get confidenceLabel() {
        const c = this.props.closingForecast?.confidence;
        if (c === "reliable") return _t("Confiable");
        if (c === "limited") return _t("Limitado");
        return _t("No disponible");
    }

    get riskClass() {
        const risk = this.props.goal?.risk;
        if (risk === "critical") return "gn-sd-goal__risk--danger";
        if (risk === "warning") return "gn-sd-goal__risk--warning";
        return "gn-sd-goal__risk--success";
    }

    get actualPct() {
        const g = this.props.goal;
        if (!g?.target) return 0;
        return Math.min((g.actual / g.target) * 100, 100);
    }

    get projectionPct() {
        const g = this.props.goal;
        if (!g?.target || !g?.projection) return 0;
        return Math.min((g.projection / g.target) * 100, 120);
    }

    onConfigureClick(ev) {
        ev.stopPropagation();
        const action = this.props.goal?.configure_action;
        if (action && this.props.onConfigure) {
            this.props.onConfigure(action);
        }
    }
}
