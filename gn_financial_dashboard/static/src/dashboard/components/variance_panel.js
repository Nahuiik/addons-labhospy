/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * Panel de variaciones (V20 Fase 1, #7).
 *
 * Muestra los KPIs con mayor variación vs. período comparativo, descomponiendo
 * el delta por cuenta y tercero. Reutiliza el estilo del panel de análisis.
 *
 * Props:
 *  - items: salida de _variance_analysis (lista de objetos con kpi, label,
 *    current, previous, delta, delta_pct, direction, accounts[], partners[],
 *    narrative).
 *  - currencySymbol: símbolo de la moneda para formatear montos.
 *  - onAccountClick(account_id, kpi): drill-down al apunte contable.
 *  - onPartnerClick(partner_id, kpi): drill-down al tercero.
 */
export class VariancePanel extends Component {
    static template = "gn_financial_dashboard.VariancePanel";
    static props = {
        items: Array,
        currencySymbol: { type: String, optional: true },
        onAccountClick: { type: Function, optional: true },
        onPartnerClick: { type: Function, optional: true },
    };

    fmt(value) {
        const symbol = this.props.currencySymbol || "";
        const sign = (value || 0) >= 0 ? "+" : "";
        return `${sign}${symbol}${Number(value || 0).toLocaleString("en-US", {
            maximumFractionDigits: 0,
        })}`;
    }

    pctTxt(item) {
        if (item.delta_pct === null || item.delta_pct === undefined) {
            return "";
        }
        const s = item.delta_pct >= 0 ? "+" : "";
        return ` (${s}${item.delta_pct.toFixed(1)}%)`;
    }

    directionCls(item) {
        // Para gastos/costo una subida es mala; para utilidad/ingresos al revés.
        const negativeKpis = ["cogs", "expenses"];
        const isBad = negativeKpis.includes(item.kpi)
            ? item.direction === "up"
            : item.direction === "down";
        return isBad ? "gn-fd-variance__delta--bad" : "gn-fd-variance__delta--good";
    }

    onAccountClick(row, item) {
        if (this.props.onAccountClick) {
            this.props.onAccountClick(row.account_id, item.kpi);
        }
    }

    onPartnerClick(row, item) {
        if (this.props.onPartnerClick) {
            this.props.onPartnerClick(row.partner_id, item.kpi);
        }
    }
}
