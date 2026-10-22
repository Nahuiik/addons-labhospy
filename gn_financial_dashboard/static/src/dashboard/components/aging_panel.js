/** @odoo-module **/

import { Component } from "@odoo/owl";
import { FinancialChart } from "../financial_chart";
import { formatMoney } from "../chart_helpers";

/**
 * Panel de cartera por antigüedad: gráfico de barras con semáforo por tramo
 * y tabla con monto y % de participación.
 *
 * Props:
 *  - title, icon, total, currencySymbol.
 *  - data: { labels, values, pct, colors, total, overdue, over_120 }.
 *  - chartConfig + fingerprint para el gráfico.
 *  - actionLabel + onAction: drill-down opcional.
 */
export class AgingPanel extends Component {
    static template = "gn_financial_dashboard.AgingPanel";
    static components = { FinancialChart };
    static props = {
        title: String,
        icon: { type: String, optional: true },
        data: Object,
        chartConfig: Object,
        fingerprint: { type: String, optional: true },
        currencySymbol: { type: String, optional: true },
        actionLabel: { type: String, optional: true },
        onAction: { type: Function, optional: true },
        onBucketClick: { type: Function, optional: true },
    };

    get rows() {
        const d = this.props.data || {};
        const labels = d.labels || [];
        return labels.map((label, i) => ({
            label,
            amount: formatMoney(d.values?.[i] ?? 0, this.props.currencySymbol || "$"),
            pct: `${(d.pct?.[i] ?? 0).toFixed(1)}%`,
            color: d.colors?.[i] || "#9ca3af",
        }));
    }
}
