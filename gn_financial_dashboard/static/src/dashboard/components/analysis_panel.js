/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * Panel de "Análisis financiero automático".
 *
 * Presenta los comentarios generados en backend (reutilizables en PDF/Excel).
 *
 * Props:
 *  - notes: [{ tone, text }].
 *  - title, icon.
 */
export class AnalysisPanel extends Component {
    static template = "gn_financial_dashboard.AnalysisPanel";
    static props = {
        notes: Array,
        title: { type: String, optional: true },
        icon: { type: String, optional: true },
    };

    iconFor(tone) {
        return {
            positive: "fa-check-circle",
            negative: "fa-times-circle",
            warning: "fa-exclamation-triangle",
            info: "fa-info-circle",
        }[tone] || "fa-info-circle";
    }
}
