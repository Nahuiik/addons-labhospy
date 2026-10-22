/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * Tabla de inteligencia de entidades (V20 Fase 3).
 *
 * Renderiza una lista ordenada de productos / clientes / proveedores con
 * scoring opcional, badges (ABC o tier), barra de progreso (concentración
 * o margen) y acciones de drill-down.
 *
 * Props:
 *  - kind: "product" | "customer" | "supplier"
 *  - items: Array<Object>
 *  - columns: Array<{key, label, format, align, width}>
 *  - currencySymbol: String
 *  - onRowClick: Function (opcional)
 */
export class IntelligenceTable extends Component {
    static template = "gn_financial_dashboard.IntelligenceTable";
    static props = {
        kind: String,
        items: Array,
        columns: Array,
        currencySymbol: { type: String, optional: true },
        onRowClick: { type: Function, optional: true },
        emptyHint: { type: String, optional: true },
    };

    fmt(value, format) {
        if (value === null || value === undefined) return "—";
        const n = Number(value);
        if (Number.isNaN(n)) return value;
        switch (format) {
            case "money":
                return (this.props.currencySymbol || "") +
                       n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            case "percent":
                return n.toFixed(1) + "%";
            case "days":
                return n.toFixed(0) + " d";
            case "int":
                return n.toLocaleString("en-US", { maximumFractionDigits: 0 });
            case "qty":
                return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
            case "score":
                return n.toFixed(0);
            default:
                return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
        }
    }

    cellValue(item, col) {
        // Soporta claves anidadas con punto (p.ej. "subscores.value")
        const path = col.key.split(".");
        let value = item;
        for (const k of path) {
            value = value?.[k];
            if (value === undefined) break;
        }
        return this.fmt(value, col.format);
    }

    badgeCls(item) {
        if (item.abc) {
            return "gn-fd-badge gn-fd-badge--abc-" + item.abc.toLowerCase();
        }
        if (item.tier) {
            return "gn-fd-badge gn-fd-badge--tier-" + item.tier;
        }
        return "";
    }

    badgeLabel(item) {
        return item.abc || (item.tier && item.tier.charAt(0).toUpperCase() + item.tier.slice(1)) || "";
    }

    rowCls(item) {
        if (item.score !== undefined && item.score < 35) return "gn-fd-irow gn-fd-irow--critical";
        if (item.margin !== undefined && item.margin < 0) return "gn-fd-irow gn-fd-irow--loss";
        return "gn-fd-irow";
    }

    onRowClick(item) {
        if (this.props.onRowClick) this.props.onRowClick(item);
    }
}
