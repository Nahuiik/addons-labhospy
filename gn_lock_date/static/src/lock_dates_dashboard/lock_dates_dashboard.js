/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

export class LockDatesDashboard extends Component {
    static template = "gn_lock_date.LockDatesDashboard";
    static components = { Layout };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");

        this.state = useState({
            loading: true,
            summary: null,
            error: null,
            companyId: user.activeCompany?.id || user.defaultCompany?.id,
        });

        onWillStart(async () => {
            await this.refresh();
        });
    }

    get display() {
        return { controlPanel: {} };
    }

    get companies() {
        return user.allowedCompanies || [];
    }

    get multiCompany() {
        return (this.companies?.length || 0) > 1;
    }

    async refresh() {
        const cid = this.state.companyId;
        if (!cid) {
            this.state.loading = false;
            this.state.error = _t("No company selected.");
            return;
        }
        this.state.loading = true;
        this.state.error = null;
        try {
            const summary = await this.orm.call("res.company", "get_all_lock_summary", [[cid]]);
            this.state.summary = summary;
        } catch (e) {
            this.state.error = e.message || String(e);
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    onCompanyChange(ev) {
        const val = Number(ev.target.value);
        if (val) {
            this.state.companyId = val;
            this.refresh();
        }
    }

    openUpdateWizard() {
        this.action.doAction({
            type: "ir.actions.client",
            tag: "gn_lock_date.lock_journal_entries",
            target: "new",
            name: "Bloquear asientos contables",
        });
    }

    openPeriodLocks() {
        this.action.doAction("gn_lock_date.action_gn_period_lock");
    }

    openExceptions() {
        this.action.doAction("gn_lock_date.action_account_lock_exception_gn");
    }

    onRevokeClick(ev) {
        const id = Number(ev.currentTarget.dataset.id);
        if (id) {
            this.revokeException(id);
        }
    }

    revokeException(exceptionId) {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Revoke exception"),
            body: _t("Revoke this lock date exception for the selected user scope?"),
            confirm: async () => {
                await this.orm.call("account.lock_exception", "action_revoke", [[exceptionId]]);
                this.notification.add(_t("Exception revoked."), { type: "success" });
                await this.refresh();
                return true;
            },
            confirmLabel: _t("Revoke"),
            cancel: () => {},
        });
    }
}

registry.category("actions").add("gn_lock_date.dashboard", LockDatesDashboard);
