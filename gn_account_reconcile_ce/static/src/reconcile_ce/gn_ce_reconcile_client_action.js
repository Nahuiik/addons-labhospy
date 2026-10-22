/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, onWillStart, useRef, onWillUnmount, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class GnCeReconcileWorkspace extends Component {
    static template = "gn_account_reconcile_ce.GnCeReconcileWorkspace";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.ce = useService("gn_account_reconcile_ce");
        this.rootRef = useRef("ceRoot");
        this.meta = useState({
            journals: [],
            journalIdInput: "",
            stViewport: { slice: [], paddingTop: 0, paddingBottom: 0 },
        });
        this._kbdUnmount = () => {};

        onWillStart(async () => {
            this.meta.journals = await this.orm.searchRead(
                "account.journal",
                [["type", "=", "bank"]],
                ["id", "name"],
                { order: "company_id,name asc", limit: 120 }
            );
            const def = this.props.action?.context?.default_journal_id;
            if (def) {
                this.meta.journalIdInput = String(def);
            }
        });

        onMounted(() => {
            const el = this.rootRef.el;
            if (!el) {
                return;
            }
            el.focus({ preventScroll: true });
            this._kbdUnmount = this.ce.attachKeyboard(el);
            this.paintStatementViewport(el.querySelector(".o_gn_ce_st_scroll") || el);
            const autoZero = Boolean(this.props.action?.context?.gn_ce_auto_zero);
            if (autoZero && this.meta.journalIdInput) {
                void this.confirmJournal().then(() => this.ce.zeroClickActive());
            }
        });

        onWillUnmount(() => {
            this._kbdUnmount();
        });
    }

    get st() {
        return this.ce.state;
    }

    fmtScore(record) {
        const v = record?.composite ?? 0;
        if (typeof v === "number") {
            return v.toFixed(2);
        }
        return `${v}`;
    }

    paintStatementViewport(scrollEl = null, scrollTop = 0) {
        const box = scrollEl || this.rootRef.el?.querySelector(".o_gn_ce_st_scroll");
        const scroll = scrollEl instanceof HTMLElement ? scrollTop : box?.scrollTop || 0;
        const geo = this.ce.sliceStatementsViewport(scroll);
        this.meta.stViewport.slice = geo.slice;
        this.meta.stViewport.paddingTop = geo.paddingTop;
        this.meta.stViewport.paddingBottom = geo.paddingBottom;
        if (!scrollEl && box) {
            box.scrollTop = 0;
        }
    }

    async confirmJournal() {
        const jid = Number(this.meta.journalIdInput);
        if (!jid) {
            return;
        }
        await this.ce.loadJournal(jid);
        this.paintStatementViewport(undefined, 0);
    }

    async pickStatement(lineId) {
        await this.ce.activateStatement(lineId);
        this.paintStatementViewport(undefined, 0);
    }

    async onReconcileClicked() {
        await this.ce.reconcileFocused();
        this.paintStatementViewport(undefined, 0);
    }

    candRows() {
        return this.ce.windowedCandidates();
    }
}

registry.category("actions").add("gn_ce_reconcile_workspace", GnCeReconcileWorkspace);
