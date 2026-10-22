/** @odoo-module **/

import { Component } from "@odoo/owl";
import { formatMonetary } from "@web/views/fields/formatters";
import { kpiVariationClass } from "./kpi_semantics";

export class SalesKpiCard extends Component {
    static template = "gn_sales_dashboard.SalesKpiCard";
    static props = {
        kpi: Object,
        currencyId: { type: Number, optional: true },
        size: { type: String, optional: true },
        onClick: { type: Function, optional: true },
    };

    get isPrimary() {
        return this.props.size === "primary" || this.props.kpi?.tier === "primary";
    }

    get isCompact() {
        return this.props.size === "secondary" || this.props.kpi?.tier === "secondary";
    }

    get formattedValue() {
        const k = this.props.kpi;
        if (!k.has_data && k.empty_reason) {
            return "—";
        }
        const v = k.display_value ?? k.value ?? 0;
        if (k.format === "currency") {
            return formatMonetary(v, { currencyId: this.props.currencyId });
        }
        if (k.format === "percent") {
            return `${Number(v).toFixed(1)}%`;
        }
        return Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 });
    }

    get variationLabel() {
        if (!this.props.kpi.has_data && this.props.kpi.empty_reason) {
            return this.props.kpi.empty_reason;
        }
        const pct = this.props.kpi.variation_pct ?? 0;
        const sign = pct > 0 ? "+" : "";
        return `${sign}${Number(pct).toFixed(1)}% vs anterior`;
    }

    get variationClass() {
        return kpiVariationClass(this.props.kpi);
    }

    get accentClass() {
        const tone = this.props.kpi?.semantic_tone || this.props.kpi?.tone || "neutral";
        return `gn-sd-kpi__accent--${tone === "success" ? "success" : tone === "danger" ? "danger" : tone === "warning" ? "warning" : "neutral"}`;
    }

    get cardClass() {
        let cls = "gn-sd-kpi";
        cls += this.isPrimary ? " gn-sd-kpi--primary" : " gn-sd-kpi--secondary";
        return cls;
    }

    get sparklinePath() {
        const pts = this.props.kpi.sparkline || [];
        if (pts.length < 2) return "";
        const w = this.isPrimary ? 120 : 72;
        const h = this.isPrimary ? 32 : 24;
        const max = Math.max(...pts, 1);
        const min = Math.min(...pts, 0);
        const range = max - min || 1;
        return pts.map((v, i) => {
            const x = (i / (pts.length - 1)) * w;
            const y = h - ((v - min) / range) * h;
            return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
        }).join(" ");
    }

    get progressPct() {
        const k = this.props.kpi;
        if (!k.target || !k.has_data) return 0;
        return Math.min(Number(k.value) || 0, 100);
    }

    onCardClick(ev) {
        if (this.props.onClick) {
            this.props.onClick(this.props.kpi);
        }
    }

    onCardKeydown(ev) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.onCardClick(ev);
        }
    }
}
