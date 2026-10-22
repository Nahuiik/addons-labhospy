/** @odoo-module **/

import { Component } from "@odoo/owl";

export class BanksWeeklyBalanceKpiCard extends Component {
    static template = "gn_banks_balance.BanksWeeklyBalanceKpiCard";
    static props = {
        label: String,
        value: String,
        subValue: { type: String, optional: true },
        icon: { type: String, optional: true },
        tone: { type: String, optional: true },
        tooltip: { type: String, optional: true },
        size: { type: String, optional: true },
        trend: { type: String, optional: true },
    };

    get toneClass() {
        const tone = this.props.tone || "neutral";
        return `gn-wb-kpi--${tone}`;
    }

    get sizeClass() {
        return this.props.size === "secondary" ? "gn-wb-kpi--secondary" : "gn-wb-kpi--primary";
    }

    get trendIcon() {
        if (this.props.trend === "up") {
            return "fa-arrow-up";
        }
        if (this.props.trend === "down") {
            return "fa-arrow-down";
        }
        if (this.props.trend === "flat") {
            return "fa-minus";
        }
        return "";
    }

    get trendClass() {
        if (this.props.trend === "up") {
            return "gn-wb-kpi__trend--up";
        }
        if (this.props.trend === "down") {
            return "gn-wb-kpi__trend--down";
        }
        return "gn-wb-kpi__trend--flat";
    }
}
