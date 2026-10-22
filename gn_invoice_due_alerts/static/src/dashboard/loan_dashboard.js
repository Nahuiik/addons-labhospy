/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { fmtMoney, rpcErrorMessage } from "./dashboard_utils";

const CARD_ORDER = [
    "overdue",
    "today",
    "due_1_7",
    "due_8_15",
    "al_dia",
    "paid",
    "total",
];

export class LoanDashboard extends Component {
    static template = "gn_invoice_due_alerts.LoanDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            error: null,
            data: null,
            filter: "all",
            expanded: {},
        });
        onWillStart(async () => {
            await this.loadData();
        });
    }

    get cardOrder() {
        return CARD_ORDER;
    }

    cardIcon(key) {
        return {
            overdue: "fa-times-circle",
            today: "fa-bell",
            due_1_7: "fa-exclamation-circle",
            due_8_15: "fa-clock-o",
            al_dia: "fa-check-circle",
            paid: "fa-check-square-o",
            total: "fa-university",
        }[key] || "fa-file";
    }

    cardHelp(key) {
        return {
            overdue: _t(
                "Cuota del mes NO pagada y su día de pago ya pasó. Requiere acción inmediata: registrar el débito en Bancos."
            ),
            today: _t(
                "La cuota del mes vence justamente hoy y aún no se ha registrado el pago (débito bancario)."
            ),
            due_1_7: _t(
                "Cuota pendiente cuyo día de pago ocurre dentro de los próximos 1 a 7 días."
            ),
            due_8_15: _t(
                "Cuota pendiente cuyo día de pago ocurre dentro de los próximos 8 a 15 días."
            ),
            al_dia: _t(
                "Cuota del mes aún pendiente, pero faltan más de 15 días para su vencimiento. Sin urgencia."
            ),
            paid: _t(
                "Ya se registró el débito bancario de la cuota de este mes. La cuota está saldada."
            ),
            total: _t(
                "Suma de todos los préstamos activos y el total de sus cuotas mensuales."
            ),
        }[key] || "";
    }

    async loadData() {
        this.state.loading = true;
        this.state.error = null;
        try {
            this.state.data = await this.orm.call(
                "gn.loan.due.alert",
                "get_loan_dashboard_data",
                []
            );
            const expanded = {};
            for (const bank of this.state.data.banks || []) {
                expanded[bank.name] = true;
            }
            this.state.expanded = expanded;
        } catch (error) {
            this.state.error = rpcErrorMessage(error);
        } finally {
            this.state.loading = false;
        }
    }

    newLoan() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Nuevo préstamo"),
            res_model: "gn.bank.loan",
            views: [[false, "form"]],
            target: "current",
        });
    }

    setFilter(key) {
        this.state.filter = key;
    }

    onCardClick(key) {
        if (key !== "total") {
            this.setFilter(key);
        }
    }

    get filteredLines() {
        const data = this.state.data;
        if (!data || !data.lines) {
            return [];
        }
        if (this.state.filter === "all") {
            return data.lines;
        }
        return data.lines.filter((line) => line.bucket === this.state.filter);
    }

    get groupedBanks() {
        const currency = (this.state.data && this.state.data.currency) || {};
        const map = {};
        for (const line of this.filteredLines) {
            const key = line.bank || _t("Sin banco");
            if (!map[key]) {
                map[key] = {
                    id: key,
                    name: key,
                    count: 0,
                    total: 0,
                    lines: [],
                };
            }
            map[key].count += 1;
            map[key].total += line.monthly_fee;
            map[key].lines.push(line);
        }
        return Object.values(map)
            .map((group) => ({
                ...group,
                total_str: fmtMoney(group.total, currency),
            }))
            .sort((a, b) => b.total - a.total);
    }

    isGroupOpen(bankName) {
        return this.state.expanded[bankName] !== false;
    }

    toggleGroup(bankName, ev) {
        if (ev) {
            ev.stopPropagation();
        }
        this.state.expanded = {
            ...this.state.expanded,
            [bankName]: !this.isGroupOpen(bankName),
        };
    }

    async onReload() {
        await this.loadData();
    }

    openLoan(id, ev) {
        if (ev) {
            ev.stopPropagation();
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "gn.bank.loan",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    registerDebit(id, ev) {
        if (ev) {
            ev.stopPropagation();
        }
        this.openLoan(id, ev);
    }

    bucketClass(bucket) {
        return {
            paid: "o_gn_loan_paid",
            today: "o_gn_loan_today",
            due_1_7: "o_gn_loan_due_1_7",
            due_8_15: "o_gn_loan_due_8_15",
            overdue: "o_gn_loan_overdue",
            al_dia: "o_gn_loan_al_dia",
        }[bucket] || "";
    }
}

registry.category("actions").add("gn_loan_due_dashboard", LoanDashboard);
