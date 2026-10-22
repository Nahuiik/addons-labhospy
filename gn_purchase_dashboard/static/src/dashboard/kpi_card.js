/** @odoo-module **/

import { Component, onPatched, useState } from "@odoo/owl";
import { formatMonetary } from "@web/views/fields/formatters";
import { kpiVariationClass } from "./kpi_semantics";
import { _t } from "@web/core/l10n/translation";

export class PurchaseKpiCard extends Component {
    static template = "gn_purchase_dashboard.PurchaseKpiCard";
    static props = {
        kpi: Object,
        currencyId: { type: Number, optional: true },
        size: { type: String, optional: true },
        onClick: { type: Function, optional: true },
        lastUpdate: { type: String, optional: true },
    };

    setup() {
        this._prevValue = this.props.kpi?.value;
        this.state = useState({ pulse: false });
        onPatched(() => {
            const v = this.props.kpi?.value;
            if (v !== this._prevValue) {
                this._prevValue = v;
                this.state.pulse = true;
                setTimeout(() => { this.state.pulse = false; }, 600);
            }
        });
    }

    get pulseClass() {
        return this.state.pulse;
    }

    get isPrimary() {
        return this.props.size === "primary" || this.props.kpi?.tier === "primary";
    }

    get formattedValue() {
        const k = this.props.kpi;
        const v = k.display_value ?? k.value ?? 0;
        if (k.format === "currency") {
            return formatMonetary(v, { currencyId: this.props.currencyId });
        }
        if (k.format === "days") {
            return `${Number(v).toFixed(1)} d`;
        }
        return Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 });
    }

    get variationLabel() {
        const pct = this.props.kpi.variation_pct ?? 0;
        const sign = pct > 0 ? "+" : "";
        return `${sign}${Number(pct).toFixed(1)}%`;
    }

    get updatedLabel() {
        return this.props.lastUpdate ? _t("Act. %s", this.props.lastUpdate) : "";
    }

    get variationClass() {
        return kpiVariationClass(this.props.kpi);
    }

    get cardClass() {
        return `gn-pd-kpi ${this.isPrimary ? "gn-pd-kpi--primary" : "gn-pd-kpi--secondary"}`;
    }

    get sparklinePath() {
        const pts = this.props.kpi.sparkline || [];
        if (pts.length < 2) return "";
        const w = this.isPrimary ? 120 : 72;
        const h = this.isPrimary ? 36 : 28;
        const max = Math.max(...pts, 1);
        const min = Math.min(...pts, 0);
        const range = max - min || 1;
        return pts.map((v, i) => {
            const x = (i / (pts.length - 1)) * w;
            const y = h - ((v - min) / range) * h;
            return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
        }).join(" ");
    }

    onCardClick() {
        if (this.props.onClick) this.props.onClick(this.props.kpi);
    }

    onCardKeydown(ev) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.onCardClick();
        }
    }
}
