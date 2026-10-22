/** @odoo-module **/

import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Barra de progreso alineada visualmente con gn_banks (LiquidationImportProgress):
 * card + progress 24px + rayas animadas + texto de fase.
 * Eventos bus gn_qif_progress (servidor con commit durante el RPC).
 */
export const gnQifProgressService = {
    dependencies: ["bus_service"],
    start(env, { bus_service }) {
        let root = null;
        let bar = null;
        let phaseEl = null;
        let pctEl = null;
        let detailEl = null;

        function ensureOverlay() {
            if (root) {
                return;
            }
            root = browser.document.createElement("div");
            root.className =
                "o_gn_qif_progress_overlay position-fixed top-0 start-0 w-100";
            root.style.cssText = "z-index: 99999; pointer-events: none;";

            const card = browser.document.createElement("div");
            card.className = "card shadow-sm m-3";
            const body = browser.document.createElement("div");
            body.className = "card-body py-3";

            const header = browser.document.createElement("div");
            header.className = "d-flex justify-content-between align-items-center mb-2 flex-wrap gap-2";

            const titleWrap = browser.document.createElement("div");
            titleWrap.className = "d-flex align-items-center gap-2";
            const h = browser.document.createElement("span");
            h.className = "fw-bold";
            h.textContent = _t("Importar EC con IA");
            phaseEl = browser.document.createElement("span");
            phaseEl.className = "text-muted";
            phaseEl.textContent = _t("Procesando...");
            titleWrap.appendChild(h);
            titleWrap.appendChild(phaseEl);

            pctEl = browser.document.createElement("span");
            pctEl.className = "fs-6 text-primary fw-bold";
            pctEl.textContent = "0%";

            header.appendChild(titleWrap);
            header.appendChild(pctEl);

            const barWrap = browser.document.createElement("div");
            barWrap.className = "progress mb-2";
            barWrap.style.height = "24px";
            bar = browser.document.createElement("div");
            bar.className =
                "progress-bar progress-bar-striped progress-bar-animated bg-primary";
            bar.setAttribute("role", "progressbar");
            bar.style.width = "0%";
            bar.setAttribute("aria-valuenow", "0");
            bar.setAttribute("aria-valuemin", "0");
            bar.setAttribute("aria-valuemax", "100");
            bar.textContent = "0%";
            barWrap.appendChild(bar);

            detailEl = browser.document.createElement("div");
            detailEl.className = "mt-2 text-muted small text-truncate";
            detailEl.style.maxWidth = "100%";

            body.appendChild(header);
            body.appendChild(barWrap);
            body.appendChild(detailEl);
            card.appendChild(body);
            root.appendChild(card);
            browser.document.body.appendChild(root);
        }

        function hideOverlay(delayMs) {
            browser.setTimeout(() => {
                if (root && root.parentNode) {
                    root.parentNode.removeChild(root);
                }
                root = null;
                bar = null;
                phaseEl = null;
                pctEl = null;
                detailEl = null;
            }, delayMs);
        }

        function setDetailProcessing(message) {
            if (!detailEl) {
                return;
            }
            detailEl.replaceChildren();
            const ic = browser.document.createElement("i");
            ic.className = "fa fa-spinner fa-spin me-1 text-primary";
            ic.setAttribute("title", _t("En curso"));
            ic.setAttribute("aria-hidden", "true");
            detailEl.appendChild(ic);
            if (message) {
                detailEl.appendChild(browser.document.createTextNode(message));
            }
        }

        bus_service.subscribe("gn_qif_progress", (payload) => {
            const { progress, message, done } = payload || {};
            if (done) {
                if (bar) {
                    bar.style.width = "100%";
                    bar.textContent = "100%";
                    bar.setAttribute("aria-valuenow", "100");
                    bar.classList.remove("progress-bar-animated");
                }
                if (pctEl) {
                    pctEl.textContent = "100%";
                }
                if (phaseEl) {
                    phaseEl.textContent = _t("Completado");
                }
                if (detailEl) {
                    detailEl.replaceChildren();
                    const ok = browser.document.createElement("i");
                    ok.className = "fa fa-check-circle text-success me-1";
                    ok.setAttribute("title", _t("Listo"));
                    ok.setAttribute("aria-hidden", "true");
                    detailEl.appendChild(ok);
                    if (message) {
                        detailEl.appendChild(
                            browser.document.createTextNode(message),
                        );
                    }
                }
                hideOverlay(900);
                return;
            }
            ensureOverlay();
            const p = Math.min(100, Math.max(0, Number(progress) || 0));
            if (bar) {
                bar.style.width = `${p}%`;
                bar.textContent = `${Math.round(p)}%`;
                bar.setAttribute("aria-valuenow", String(Math.round(p)));
            }
            if (pctEl) {
                pctEl.textContent = `${Math.round(p)}%`;
            }
            if (phaseEl && p < 100) {
                phaseEl.textContent = _t("Procesando...");
            }
            setDetailProcessing(message || "");
        });
        bus_service.start();
    },
};

registry.category("services").add("gn_qif_progress", gnQifProgressService);

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        useService("gn_qif_progress");
    },
});
