/** @odoo-module **/

import { Component } from "@odoo/owl";

const VARIANTS = {
    empty: {
        icon: "fa-bar-chart",
        defaultMessage: "No hubo movimientos suficientes para generar análisis.",
    },
    unavailable: {
        icon: "fa-cog",
        defaultMessage: "No es posible calcular este indicador porque faltan cuentas configuradas.",
    },
    no_activity: {
        icon: "fa-minus-circle",
        defaultMessage: "No se registraron movimientos durante el período.",
    },
    error: {
        icon: "fa-exclamation-circle",
        defaultMessage: "No fue posible cargar el análisis.",
    },
};

export class DashboardStatePanel extends Component {
    static template = "gn_banks_balance.DashboardStatePanel";
    static props = {
        variant: { type: String, optional: true },
        message: { type: String, optional: true },
        icon: { type: String, optional: true },
        compact: { type: Boolean, optional: true },
        onRetry: { type: Function, optional: true },
    };

    get config() {
        return VARIANTS[this.props.variant || "empty"] || VARIANTS.empty;
    }

    get iconClass() {
        return this.props.icon || this.config.icon;
    }

    get message() {
        return this.props.message || this.config.defaultMessage;
    }
}

/** @deprecated alias */
export class BanksWeeklyBalanceEmptyState extends DashboardStatePanel {
    static props = {
        message: String,
        icon: { type: String, optional: true },
        variant: { type: String, optional: true },
    };
}
