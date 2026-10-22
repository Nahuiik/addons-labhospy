/** @odoo-module **/

import { Component } from "@odoo/owl";
import { formatMoney, formatPct } from "./format_utils";

export class InvPayKpiCard extends Component {
    static template = "gn_accounting_reports.InvPayKpiCard";
    static props = {
        card: Object,
        currencyId: { type: Number, optional: true },
        currencySymbol: { type: String, optional: true },
    };

    get displayValue() {
        const c = this.props.card;
        if (c.is_pct) return formatPct(c.value);
        if (c.is_count || c.is_days) return String(Math.round(c.value * 10) / 10);
        return formatMoney(c.value, this.props.currencyId);
    }

    get fullValue() {
        const c = this.props.card;
        if (c.is_pct) return formatPct(c.value, 2);
        if (c.is_count || c.is_days) return String(Math.round(c.value * 10) / 10);
        return formatMoney(c.value, this.props.currencyId);
    }

    get toneClass() {
        const tones = {
            info: "o_inv_pay_kpi--info",
            success: "o_inv_pay_kpi--success",
            warning: "o_inv_pay_kpi--warning",
            danger: "o_inv_pay_kpi--danger",
            primary: "o_inv_pay_kpi--primary",
            neutral: "o_inv_pay_kpi--neutral",
        };
        return tones[this.props.card.tone] || tones.neutral;
    }

    get deltaLabel() {
        const d = this.props.card.delta;
        if (!d) return null;
        if (d.label) return d.label;
        if (d.is_pp && d.pp !== null && d.pp !== undefined) {
            const arrow = d.pp >= 0 ? "▲" : "▼";
            const sign = d.pp >= 0 ? "+" : "";
            return `${arrow} ${sign}${Math.abs(d.pp).toFixed(1)} pp`;
        }
        if (d.pct === null || d.pct === undefined) return null;
        const arrow = d.pct >= 0 ? "▲" : "▼";
        return `${arrow} ${Math.abs(d.pct).toFixed(1)} %`;
    }

    get deltaClass() {
        const d = this.props.card.delta;
        if (!d) return "";
        const val = d.is_pp ? d.pp : d.pct;
        if (val === null || val === undefined) return "text-muted";
        return val >= 0 ? "text-success" : "text-danger";
    }
}
