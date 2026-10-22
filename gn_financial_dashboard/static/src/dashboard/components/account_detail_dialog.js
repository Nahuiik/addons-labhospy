/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { formatMoney } from "../chart_helpers";

/**
 * Diálogo de detalle por cuenta para un KPI.
 *
 * Muestra, por cuenta contable: código, nombre, tipo, saldo del período,
 * saldo del período anterior, variación absoluta y %, y compañía.
 *
 * Si hay más de 5 cuentas y varios tipos contables (account_type), agrupa
 * por tipo con un encabezado colapsable + total por grupo, para ofrecer
 * una vista de árbol básica (KPI → tipo → cuenta → apuntes).
 *
 * Props:
 *  - title: encabezado.
 *  - detail: { rows, currency, has_compare }.
 *  - onOpenLines: callback opcional para abrir los apuntes de una cuenta.
 *  - close: inyectado por el servicio de diálogos.
 */
export class AccountDetailDialog extends Component {
    static template = "gn_financial_dashboard.AccountDetailDialog";
    static components = { Dialog };
    static props = {
        title: String,
        detail: Object,
        onOpenLines: { type: Function, optional: true },
        close: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({ collapsed: {} });
    }

    get symbol() {
        return this.props.detail.currency?.symbol || "$";
    }

    /** Activa la vista agrupada cuando hay suficiente datos. */
    get useGrouped() {
        const rows = this.props.detail?.rows || [];
        if (rows.length < 6) return false;
        const types = new Set(rows.map(r => r.account_type).filter(Boolean));
        return types.size >= 2;
    }

    /** Devuelve los grupos por tipo, con total y filas ordenadas por |balance|. */
    get groups() {
        const rows = [...(this.props.detail?.rows || [])];
        const groupsMap = {};
        for (const r of rows) {
            const key = r.account_type || "—";
            if (!groupsMap[key]) {
                groupsMap[key] = { key, label: this._typeLabel(key), rows: [], total: 0, prev_total: 0 };
            }
            groupsMap[key].rows.push(r);
            groupsMap[key].total += Number(r.balance || 0);
            groupsMap[key].prev_total += Number(r.prev_balance || 0);
        }
        const groups = Object.values(groupsMap);
        for (const g of groups) {
            g.rows.sort((a, b) => Math.abs(b.balance || 0) - Math.abs(a.balance || 0));
        }
        groups.sort((a, b) => Math.abs(b.total) - Math.abs(a.total));
        return groups;
    }

    _typeLabel(t) {
        // Etiquetas legibles para account_type del estándar contable.
        const map = {
            income: "Ingresos",
            income_other: "Otros ingresos",
            expense: "Gastos",
            expense_depreciation: "Depreciación",
            expense_direct_cost: "Costo de ventas",
            asset_receivable: "Cuentas por cobrar",
            asset_cash: "Bancos y caja",
            asset_current: "Activo corriente",
            asset_non_current: "Activo no corriente",
            asset_prepayments: "Pagos anticipados",
            liability_payable: "Cuentas por pagar",
            liability_current: "Pasivo corriente",
            liability_non_current: "Pasivo no corriente",
            equity: "Patrimonio",
            equity_unaffected: "Resultados del ejercicio",
        };
        return map[t] || t;
    }

    isCollapsed(key) {
        return this.state.collapsed[key] === true;
    }

    toggleGroup(key) {
        this.state.collapsed[key] = !this.state.collapsed[key];
    }

    expandAll() {
        for (const k of Object.keys(this.state.collapsed)) {
            this.state.collapsed[k] = false;
        }
    }
    collapseAll() {
        for (const g of this.groups) {
            this.state.collapsed[g.key] = true;
        }
    }

    fmt(value) {
        return formatMoney(value, this.symbol);
    }

    deltaCls(pct) {
        if (pct === null || pct === undefined) {
            return "text-muted";
        }
        return pct >= 0 ? "text-success" : "text-danger";
    }

    onRowClick(row) {
        if (this.props.onOpenLines) {
            this.props.onOpenLines(row);
            if (this.props.close) {
                this.props.close();
            }
        }
    }
}
