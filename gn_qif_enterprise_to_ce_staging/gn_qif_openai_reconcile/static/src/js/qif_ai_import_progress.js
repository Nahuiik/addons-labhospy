/** @odoo-module */

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class QifAiImportProgress extends Component {
    static template = "gn_qif_openai_reconcile.QifAiImportProgress";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            batchId: this.props.action.params?.batch_id,
            phase: "processing",
            progress: 0,
            total: 6,
            processed: 0,
            ok: 0,
            errors: 0,
            currentFile: "",
            processedResults: [],
            lastResult: null,
            errorDetail: "",
        });

        onMounted(() => this.startProcessing());
    }

    async startProcessing() {
        if (!this.state.batchId) {
            this.state.phase = "error";
            this.state.errorDetail = _t("No se recibió el identificador del lote.");
            return;
        }

        await this.processLoop();
    }

    async processLoop() {
        while (this.state.phase === "processing") {
            try {
                const result = await this.orm.call(
                    "gn.qif.ai.batch",
                    "process_next",
                    [[this.state.batchId]],
                );
                this.state.progress = result.progress || 0;
                this.state.processed = result.processed || 0;
                this.state.total = result.total || 6;
                this.state.ok = result.ok || 0;
                this.state.errors = result.errors || 0;

                if (result.last_result) {
                    this.state.lastResult = result.last_result;
                    this.state.currentFile = result.last_result.filename || "";
                    this.state.processedResults.push(result.last_result);
                }

                if (result.state === "error") {
                    this.state.phase = "error";
                    this.state.errorDetail =
                        result.error_message || _t("Error durante el análisis.");
                    this.notification.add(this.state.errorDetail, {
                        type: "danger",
                        sticky: true,
                    });
                    break;
                }

                if (result.state === "done") {
                    this.state.phase = "done";
                    this.notification.add(_t("Análisis completado."), {
                        type: "success",
                        sticky: false,
                    });
                    if (result.wizard_action) {
                        await this.actionService.doAction(result.wizard_action);
                    }
                    break;
                }
            } catch (e) {
                console.error("QIF AI import loop:", e);
                this.state.phase = "error";
                this.state.errorDetail = e.message || String(e);
                this.notification.add(
                    _t("Error: ") + this.state.errorDetail,
                    { type: "danger", sticky: true },
                );
                break;
            }
        }
    }

    get progressPercent() {
        return Math.round(this.state.progress);
    }

    get phaseLabel() {
        switch (this.state.phase) {
            case "processing":
                return _t("Analizando estado de cuenta…");
            case "done":
                return _t("Completado");
            case "error":
                return _t("Error");
            default:
                return "";
        }
    }
}

registry.category("actions").add("qif_ai_import_progress", QifAiImportProgress);
