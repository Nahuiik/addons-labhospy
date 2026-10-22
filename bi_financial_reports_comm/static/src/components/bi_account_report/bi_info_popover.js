/** @odoo-module **/

import { Component } from "@odoo/owl";

export class BiInfoPopover extends Component {
    static template = "bi_financial_reports_comm.BiInfoPopover";
    static props = {
        motor: { type: String, optional: true },
        label: { type: String, optional: true },
        formula: { type: String, optional: true },
        value: { type: String, optional: true },
        close: { type: Function, optional: true },
    };
}
