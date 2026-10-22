/** @odoo-module **/

import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

/**
 * Asistente IA financiero (V20 Fase 6, #23).
 *
 * Componente conversacional simple: muestra historial de Q/A y un input.
 * No mantiene estado del lado servidor; cada pregunta es independiente.
 *
 * Props:
 *  - history: Array<{role: 'user'|'assistant', text: String, intent?: String, data?: Object}>
 *  - loading: Boolean
 *  - onAsk: Function(question: String)
 *  - suggestions: Array<String> (opcional)
 */
export class ChatPanel extends Component {
    static template = "gn_financial_dashboard.ChatPanel";
    static props = {
        history: Array,
        loading: { type: Boolean, optional: true },
        onAsk: Function,
        suggestions: { type: Array, optional: true },
    };
    static defaultProps = {
        loading: false,
        suggestions: [],
    };

    setup() {
        this.state = useState({ draft: "" });
        this.inputRef = useRef("input");
        this.bodyRef = useRef("body");
        onMounted(() => this.scrollToBottom());
    }

    scrollToBottom() {
        const el = this.bodyRef.el;
        if (el) {
            el.scrollTop = el.scrollHeight;
        }
    }

    onChangeDraft(ev) {
        this.state.draft = ev.target.value;
    }

    onSubmit(ev) {
        ev.preventDefault();
        const q = (this.state.draft || "").trim();
        if (!q || this.props.loading) {
            return;
        }
        this.state.draft = "";
        this.props.onAsk(q);
        if (this.inputRef.el) {
            this.inputRef.el.focus();
        }
        setTimeout(() => this.scrollToBottom(), 50);
    }

    onSuggestionClick(text) {
        if (this.props.loading) {
            return;
        }
        this.props.onAsk(text);
        setTimeout(() => this.scrollToBottom(), 50);
    }

    intentLabel(intent) {
        return ({
            overview: _t("Resumen"),
            alerts: _t("Alertas"),
            forecast: _t("Pronóstico"),
            score: _t("Salud financiera"),
            cash: _t("Caja"),
            profit: _t("Rentabilidad"),
            sales: _t("Ventas"),
            customers: _t("Clientes"),
            suppliers: _t("Proveedores"),
            products: _t("Productos"),
            benchmark: _t("Benchmark"),
            decisions: _t("Decisiones"),
            llm: _t("Asistente"),
            noop: "",
        })[intent] || intent || "";
    }
}
