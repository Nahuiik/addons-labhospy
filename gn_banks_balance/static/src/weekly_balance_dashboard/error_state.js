/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class DashboardErrorState extends Component {
    static template = "gn_banks_balance.DashboardErrorState";
    static props = {
        message: String,
        technical: { type: String, optional: true },
        onRetry: Function,
    };

    get title() {
        return _t("No se pudo cargar el dashboard");
    }

    get retryLabel() {
        return _t("Reintentar");
    }
}
