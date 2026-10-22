/** @odoo-module **/

import { Component } from "@odoo/owl";
import { formatMonetary } from "@web/views/fields/formatters";

export class BankDetailExpandable extends Component {
    static template = "gn_banks_balance.BankDetailExpandable";
    static props = {
        week: Object,
        currencyId: Number,
        onDrilldown: Function,
    };

    fmt(amount) {
        return formatMonetary(amount ?? 0, { currencyId: this.props.currencyId });
    }

    onBankClick(bank, metric) {
        this.props.onDrilldown({
            week_no: this.props.week.week_no,
            journal_id: bank.journal_id,
            metric,
        });
    }
}
