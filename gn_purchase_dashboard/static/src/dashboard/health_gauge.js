/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { PurchaseEmptyState } from "./empty_state";

export class PurchaseHealthGauge extends Component {
    static template = "gn_purchase_dashboard.PurchaseHealthGauge";
    static components = { PurchaseEmptyState };
    static props = {
        health: { type: Object, optional: true },
        loading: { type: Boolean, optional: true },
        onFactorClick: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({ showAllFactors: false });
    }

    get score() {
        return this.props.health?.score ?? 0;
    }

    get dashOffset() {
        const pct = Math.min(100, Math.max(0, this.score)) / 100;
        return 2 * Math.PI * 48 * (1 - pct);
    }

    get statusClass() {
        const s = this.score;
        if (s >= 80) return "gn-pd-health--good";
        if (s >= 65) return "gn-pd-health--ok";
        if (s >= 45) return "gn-pd-health--warn";
        return "gn-pd-health--bad";
    }

    get topFactors() {
        const factors = [...(this.props.health?.factors || [])];
        return this.state.showAllFactors ? factors : factors.slice(0, 6);
    }

    factorBarClass(f) {
        return `gn-pd-health__bar-fill gn-pd-health__bar-fill--${f.status || "warn"}`;
    }

    toggleBreakdown() {
        this.state.showAllFactors = !this.state.showAllFactors;
    }
}
