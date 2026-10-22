/** @odoo-module **/

import { Component, useState, onWillUpdateProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const MODEL = "purchase.dashboard.service";

export class PurchaseAlertCenter extends Component {
    static template = "gn_purchase_dashboard.AlertCenter";
    static props = {
        open: Boolean,
        filters: Object,
        onClose: Function,
        onAlertClick: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ loading: false, data: { items: [], counts: {} }, filter: "all" });
        onWillUpdateProps((next) => {
            if (next.open) this.load();
        });
        if (this.props.open) this.load();
    }

    get filteredItems() {
        const items = this.state.data?.items || [];
        if (this.state.filter === "all") return items;
        return items.filter((a) => a.severity === this.state.filter);
    }

    async load() {
        if (!this.props.open) return;
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(MODEL, "get_alert_center", [this.props.filters]);
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    setFilter(filter) {
        this.state.filter = filter;
    }

    async doAction(alert, action) {
        try {
            await this.orm.call(MODEL, "update_alert_action", [alert.id, action, {
                title: alert.title,
                severity: alert.severity,
                metric: alert.metric,
            }]);
            await this.load();
            this.notification.add(_t("Alerta actualizada."), { type: "success" });
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        }
    }

    onCloseClick() {
        if (this.props.onClose) this.props.onClose();
    }
}
