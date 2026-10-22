/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

/**
 * Lista de alertas (V20 Fase 6, #21).
 *
 * Props:
 *  - alerts: Array<{code, name, severity, category, message, action_hint, ...}>
 *  - title (opcional)
 *  - onDrill (opcional) Function({code, payload})
 *  - onAcknowledge (opcional) Function(event_id)
 *  - onResolve (opcional) Function(event_id)
 *  - withPersistence: si true, muestra acciones (ack/resolve) - requiere
 *    que cada alerta tenga `event_id`.
 */
export class AlertList extends Component {
    static template = "gn_financial_dashboard.AlertList";
    static props = {
        alerts: Array,
        title: { type: String, optional: true },
        onDrill: { type: Function, optional: true },
        onAcknowledge: { type: Function, optional: true },
        onResolve: { type: Function, optional: true },
        withPersistence: { type: Boolean, optional: true },
        emptyLabel: { type: String, optional: true },
    };
    static defaultProps = {
        withPersistence: false,
    };

    severityBadge(sev) {
        return ({
            critical: "gn-fd-alert-badge gn-fd-alert-badge--critical",
            warning: "gn-fd-alert-badge gn-fd-alert-badge--warning",
            info: "gn-fd-alert-badge gn-fd-alert-badge--info",
        })[sev] || "gn-fd-alert-badge gn-fd-alert-badge--info";
    }

    severityLabel(sev) {
        return ({
            critical: _t("Crítica"),
            warning: _t("Advertencia"),
            info: _t("Info"),
        })[sev] || sev;
    }

    categoryLabel(c) {
        return ({
            liquidity: _t("Liquidez"),
            profitability: _t("Rentabilidad"),
            working_capital: _t("Capital de trabajo"),
            risk: _t("Riesgo"),
            growth: _t("Crecimiento"),
            other: _t("Otras"),
        })[c] || c || "—";
    }

    canDrill(a) {
        return !!(a.payload && (a.payload.partner_id || a.payload.product_id ||
                                a.payload.account_id || a.payload.goal_id ||
                                a.payload.kpi));
    }

    onDrillClick(a) {
        if (this.props.onDrill) {
            this.props.onDrill(a);
        }
    }

    onAckClick(a, ev) {
        ev.stopPropagation();
        if (this.props.onAcknowledge && a.event_id) {
            this.props.onAcknowledge(a.event_id);
        }
    }

    onResolveClick(a, ev) {
        ev.stopPropagation();
        if (this.props.onResolve && a.event_id) {
            this.props.onResolve(a.event_id);
        }
    }
}
