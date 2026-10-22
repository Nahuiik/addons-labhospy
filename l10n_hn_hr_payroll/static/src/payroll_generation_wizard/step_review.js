/** @odoo-module **/

import { Component } from "@odoo/owl";

export class StepReview extends Component {
    static template = "l10n_hn_hr_payroll.StepReview";
    static props = {
        config: Object,
        selectedCount: Number,
        structureName: { optional: true },
        companyName: { optional: true },
    };
}
