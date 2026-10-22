import {Component, useState} from "@odoo/owl";
import {useBus} from "@web/core/utils/hooks";

export class SelectedLineSummary extends Component {
    static props = {};
    setup() {
        this.state = useState({line: null});
        useBus(this.env.bus, "RECONCILE_LINE_SELECTED", ({detail}) => {
            this.state.line = detail || null;
        });
        useBus(this.env.bus, "RECONCILE_CLEAR_SELECTED_LINE", () => {
            this.state.line = null;
        });
    }
}

SelectedLineSummary.template = "account_reconcile_oca.SelectedLineSummary";
