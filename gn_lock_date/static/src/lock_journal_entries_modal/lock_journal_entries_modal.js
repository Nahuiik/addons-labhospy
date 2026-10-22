/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";

/** Native CE lock fields on res.company (soft locks first, hard last). */
const SOFT_LOCK_FIELDS = [
    "sale_lock_date",
    "purchase_lock_date",
    "tax_lock_date",
    "fiscalyear_lock_date",
];

export class LockJournalEntriesModal extends Component {
    static template = "gn_lock_date.LockJournalEntriesModal";
    static props = ["*"];
    static target = "new";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            saving: false,
            companyId: user.activeCompany?.id || user.defaultCompany?.id,
            sale_lock_date: "",
            purchase_lock_date: "",
            tax_lock_date: "",
            fiscalyear_lock_date: "",
            hard_lock_date: "",
        });

        this.softLockFields = SOFT_LOCK_FIELDS;
        this.fieldMeta = {
            sale_lock_date: {
                label: "Bloquear ventas",
                help: "Impide cambios en asientos de ventas hasta esta fecha.",
            },
            purchase_lock_date: {
                label: "Bloquear compras",
                help: "Impide cambios en asientos de compras hasta esta fecha.",
            },
            tax_lock_date: {
                label: "Bloquear declaración fiscal",
                help: "después de un cierre fiscal",
            },
            fiscalyear_lock_date: {
                label: "Bloquear todo",
                help: "pero permite excepciones",
            },
        };

        onWillStart(() => this.loadCompany());
    }

    meta(field) {
        return this.fieldMeta[field] || { label: field, help: "" };
    }

    get companies() {
        return user.allowedCompanies || [];
    }

    get multiCompany() {
        return (this.companies?.length || 0) > 1;
    }

    _normDate(val) {
        if (!val) {
            return "";
        }
        if (typeof val === "string" && val.length >= 10) {
            return val.slice(0, 10);
        }
        return String(val).slice(0, 10);
    }

    async loadCompany() {
        const cid = this.state.companyId;
        if (!cid) {
            this.state.loading = false;
            return;
        }
        this.state.loading = true;
        try {
            const rows = await this.orm.read("res.company", [cid], [
                ...SOFT_LOCK_FIELDS,
                "hard_lock_date",
            ]);
            const r = rows[0] || {};
            for (const f of [...SOFT_LOCK_FIELDS, "hard_lock_date"]) {
                this.state[f] = this._normDate(r[f]);
            }
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    onCompanyChange(ev) {
        const val = Number(ev.target.value);
        if (val) {
            this.state.companyId = val;
            this.loadCompany();
        }
    }

    onDateInput(field, ev) {
        this.state[field] = ev.target.value || "";
    }

    onHardLockInput(ev) {
        this.state.hard_lock_date = ev.target.value || "";
    }

    displayValue(field) {
        return this.state[field] || "No bloqueado";
    }

    async save() {
        if (!this.state.companyId) {
            return;
        }
        this.state.saving = true;
        const vals = {};
        for (const f of [...SOFT_LOCK_FIELDS, "hard_lock_date"]) {
            const v = this.state[f];
            vals[f] = v ? v : false;
        }
        try {
            await this.orm.write("res.company", [this.state.companyId], vals);
            this.notification.add(_t("Las fechas de bloqueo se han actualizado."), { type: "success" });
            await this.action.doAction({ type: "ir.actions.act_window_close" });
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    discard() {
        this.action.doAction({ type: "ir.actions.act_window_close" });
    }
}

registry.category("actions").add("gn_lock_date.lock_journal_entries", LockJournalEntriesModal);
