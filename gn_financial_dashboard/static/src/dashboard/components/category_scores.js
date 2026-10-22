/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * Tarjetas con el puntaje 0-100 por categoría del score financiero.
 *
 * Props:
 *  - categories: lista del motor de scoring (cada una con key, label,
 *    score, weight, points, criteria).
 *  - onSelect (opcional): callback al hacer clic sobre una categoría.
 */
export class CategoryScores extends Component {
    static template = "gn_financial_dashboard.CategoryScores";
    static props = {
        categories: Array,
        onSelect: { type: Function, optional: true },
    };

    iconFor(key) {
        return {
            profitability: "fa-line-chart",
            liquidity: "fa-tint",
            cashflow: "fa-exchange",
            collection: "fa-hand-holding-usd",
            leverage: "fa-balance-scale",
            data_quality: "fa-check-square-o",
        }[key] || "fa-tachometer";
    }

    levelClass(score) {
        if (score >= 80) {
            return "gn-fd-catscore--excellent";
        }
        if (score >= 60) {
            return "gn-fd-catscore--good";
        }
        if (score >= 40) {
            return "gn-fd-catscore--warning";
        }
        return "gn-fd-catscore--risk";
    }

    onClick(cat) {
        if (this.props.onSelect) {
            this.props.onSelect(cat);
        }
    }
}
