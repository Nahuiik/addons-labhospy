/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { fmtMoney, rpcErrorMessage } from "./dashboard_utils";

const CARD_ORDER = ["al_dia", "due_1_7", "due_8_15", "overdue_15", "total"];

export class TrafficDashboard extends Component {
    static template = "gn_customer_due_alerts.TrafficDashboard";
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
            al_dia: "fa-check-circle",
            due_1_7: "fa-exclamation-circle",
            due_8_15: "fa-clock-o",
            overdue_15: "fa-times-circle",
            total: "fa-list-alt",
        }[key] || "fa-file";
    }

    async loadData() {
        this.state.loading = true;
        this.state.error = null;
        try {
            this.state.data = await this.orm.call(
                "gn.customer.due.alert",
                "get_due_traffic_dashboard_data",
                []
            );
            const expanded = {};
            const seen = {};
            for (const line of this.state.data.lines || []) {
                if (!seen[line.partner_id]) {
                    seen[line.partner_id] = true;
                    expanded[line.partner_id] = true;
                }
            }
            this.state.expanded = expanded;
        } catch (error) {
            this.state.error = rpcErrorMessage(error);
        } finally {
            this.state.loading = false;
        }
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

    get groupedPartners() {
        const currency = (this.state.data && this.state.data.currency) || {};
        const map = {};
        for (const line of this.filteredLines) {
            const partnerId = line.partner_id;
            if (!map[partnerId]) {
                map[partnerId] = {
                    id: partnerId,
                    name: line.partner,
                    count: 0,
                    total: 0,
                    lines: [],
                };
            }
            map[partnerId].count += 1;
            map[partnerId].total += line.residual;
            map[partnerId].lines.push(line);
        }
        return Object.values(map)
            .map((group) => ({
                ...group,
                total_str: fmtMoney(group.total, currency),
            }))
            .sort((a, b) => b.total - a.total);
    }

    isGroupOpen(partnerId) {
        return this.state.expanded[partnerId] !== false;
    }

    toggleGroup(partnerId, ev) {
        if (ev) {
            ev.stopPropagation();
        }
        this.state.expanded = {
            ...this.state.expanded,
            [partnerId]: !this.isGroupOpen(partnerId),
        };
    }

    async onReload() {
        await this.loadData();
    }

    openBill(line, ev) {
        if (ev) {
            ev.stopPropagation();
        }
        const resId = line.source === "receivable_line" ? line.move_id : line.id;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "account.move",
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openPartner(partnerId, ev) {
        if (ev) {
            ev.stopPropagation();
        }
        const partnerName = this.groupedPartners.find((g) => g.id === partnerId)?.name;
        this.action.doAction("gn_customer_due_alerts.action_customer_due_partner_all", {
            name: partnerName ? `CxC - ${partnerName}` : undefined,
            domain: [
                ["partner_id", "=", partnerId],
                ["parent_state", "=", "posted"],
                ["account_id.account_type", "=", "asset_receivable"],
                ["reconciled", "=", false],
                ["amount_residual", ">", 0],
                ["move_id.move_type", "in", ["out_invoice", "out_refund", "entry"]],
            ],
            context: { search_default_group_partner: 0 },
        });
    }
}

registry.category("actions").add(
    "gn_customer_due_traffic_dashboard",
    TrafficDashboard
);
