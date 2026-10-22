/** @odoo-module **/

import { Component } from "@odoo/owl";

export class InvPayInsightsPanel extends Component {
    static template = "gn_accounting_reports.InvPayInsightsPanel";
    static props = {
        insights: Array,
        onAction: Function,
    };
}

export class InvPayDetailPanel extends Component {
    static template = "gn_accounting_reports.InvPayDetailPanel";
    static props = {
        detail: Object,
        open: Boolean,
        onClose: Function,
        onOpenRecord: Function,
    };
}
