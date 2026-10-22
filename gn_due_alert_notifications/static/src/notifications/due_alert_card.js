/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const LEVEL_CLASS = {
    soon: "o_gn_due_alert_soon",
    today: "o_gn_due_alert_today",
    overdue: "o_gn_due_alert_overdue",
    critical: "o_gn_due_alert_critical",
    resolved: "o_gn_due_alert_resolved",
};

export class DueAlertCard extends Component {
    static template = "gn_due_alert_notifications.DueAlertCard";
    static props = {
        card: Object,
        onClose: Function,
        onRefresh: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
    }

    get levelClass() {
        return LEVEL_CLASS[this.props.card.alert_level] || "o_gn_due_alert_soon";
    }

    get daysLabel() {
        const d = this.props.card.days_delta;
        if (d > 0) {
            return _t("Vence en %s dias").replace("%s", d);
        }
        if (d === 0) {
            return _t("Vence hoy");
        }
        return _t("Vencida hace %s dias").replace("%s", Math.abs(d));
    }

    async onOpenInvoice(ev) {
        ev.stopPropagation();
        const action = await this.orm.call(
            "gn.due.alert.engine",
            "action_open_invoice",
            [this.props.card.id]
        );
        this.action.doAction(action);
    }

    async onRegisterPayment(ev) {
        ev.stopPropagation();
        const action = await this.orm.call(
            "gn.due.alert.engine",
            "action_register_payment",
            [this.props.card.id]
        );
        this.action.doAction(action);
    }

    async onSnooze(ev) {
        ev.stopPropagation();
        await this.orm.call(
            "gn.due.alert.engine",
            "action_snooze_notification",
            [this.props.card.id]
        );
        this.props.onRefresh();
    }

    async onReview(ev) {
        ev.stopPropagation();
        await this.orm.call(
            "gn.due.alert.engine",
            "action_review_notification",
            [this.props.card.id]
        );
        this.props.onRefresh();
    }

    async onClose(ev) {
        ev.stopPropagation();
        await this.orm.call(
            "gn.due.alert.engine",
            "action_close_notification",
            [this.props.card.id]
        );
        this.props.onClose(this.props.card.id);
    }
}
