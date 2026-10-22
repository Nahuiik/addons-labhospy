/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * Tabla de ranking reutilizable.
 *
 * El contenedor entrega filas con celdas ya formateadas para mantener el
 * componente puramente presentacional.
 *
 * Props:
 *  - title, icon: encabezado del panel.
 *  - headers: [{ label, align, sortKey? }].
 *  - rows: [{ id, clickable, cells: [{ text, cls }] }].
 *  - onRowClick: callback opcional (recibe la fila completa).
 *  - sortState (opcional): { key, dir } para cabeceras ordenables.
 *  - onSort (opcional): Function(sortKey).
 *  - emptyText: texto cuando no hay filas.
 *  - actionLabel + onAction: botón de acción opcional (p. ej. "Detalle →").
 */
export class RankingTable extends Component {
    static template = "gn_financial_dashboard.RankingTable";
    static props = {
        title: String,
        icon: { type: String, optional: true },
        headers: Array,
        rows: Array,
        onRowClick: { type: Function, optional: true },
        sortState: { type: Object, optional: true },
        onSort: { type: Function, optional: true },
        emptyText: { type: String, optional: true },
        actionLabel: { type: String, optional: true },
        onAction: { type: Function, optional: true },
    };

    onRowClick(row) {
        if (this.props.onRowClick && row.clickable !== false) {
            this.props.onRowClick(row);
        }
    }

    onHeaderClick(header) {
        if (this.props.onSort && header.sortKey) {
            this.props.onSort(header.sortKey);
        }
    }

    sortIcon(header) {
        const st = this.props.sortState;
        if (!header.sortKey || !st || st.key !== header.sortKey) {
            return "fa-sort text-muted";
        }
        return st.dir === "desc" ? "fa-sort-desc" : "fa-sort-asc";
    }
}
