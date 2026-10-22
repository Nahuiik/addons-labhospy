/** @odoo-module **/

import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { formatMonetary } from "@web/views/fields/formatters";

export class MovementDrilldownModal extends Component {
    static template = "gn_banks_balance.MovementDrilldownModal";
    static components = { Dialog };
    static props = {
        close: Function,
        title: String,
        lines: Array,
        count: Number,
        currencyId: Number,
        onOpenOdoo: Function,
    };

    fmt(amount) {
        return formatMonetary(amount ?? 0, { currencyId: this.props.currencyId });
    }

    onOpenClick() {
        this.props.onOpenOdoo();
        this.props.close();
    }
}
