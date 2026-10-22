/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { browser } from "@web/core/browser/browser";

/**
 * Barra de progreso (OWL) para notificaciones `gn_qif_progress` (long-polling bus).
 */
export class GnQifProgressOverlay extends Component {
    static template = "gn_qif_openai_reconcile.GnQifProgressOverlay";

    setup() {
        this.bus = useService("bus_service");
        this._hideTimer = null;
        this._onPayload = (payload) => {
            if (!payload) {
                return;
            }
            const { progress, message, done } = payload;
            this.state.active = true;
            this.state.progress = Math.min(100, Math.max(0, Number(progress) || 0));
            this.state.message = message || "";
            this.state.done = Boolean(done);

            if (this._hideTimer) {
                browser.clearTimeout(this._hideTimer);
            }
            if (done) {
                this.state.progress = 100;
                this._hideTimer = browser.setTimeout(() => {
                    this.state.active = false;
                    this.state.message = "";
                    this.state.done = false;
                }, 900);
            }
        };
        this.state = useState({
            active: false,
            progress: 0,
            message: "",
            done: false,
        });
        onMounted(() => {
            this.bus.subscribe("gn_qif_progress", this._onPayload);
        });
        onWillUnmount(() => {
            this.bus.unsubscribe("gn_qif_progress", this._onPayload);
            if (this._hideTimer) {
                browser.clearTimeout(this._hideTimer);
            }
        });
    }

    get progressPct() {
        return Math.round(this.state.progress);
    }

    get percentLabel() {
        return `${this.progressPct}%`;
    }

    get titleText() {
        return _t("Importar EC con IA");
    }

    get phaseText() {
        if (this.state.done) {
            return _t("Completado");
        }
        if (this.state.active) {
            return _t("Procesando…");
        }
        return "";
    }

    get barClasses() {
        if (this.state.done) {
            return "progress-bar bg-success";
        }
        return "progress-bar progress-bar-striped progress-bar-animated bg-primary";
    }
}

registry.category("main_components").add("gn_qif_progress_overlay", {
    Component: GnQifProgressOverlay,
});
