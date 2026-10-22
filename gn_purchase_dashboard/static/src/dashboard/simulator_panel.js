/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary } from "@web/views/fields/formatters";

const MODEL = "purchase.dashboard.service";

export class PurchaseSimulatorPanel extends Component {
    static template = "gn_purchase_dashboard.SimulatorPanel";
    static props = {
        open: Boolean,
        filters: Object,
        currencyId: Number,
        onClose: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            scenario: "price_increase",
            percent: 8,
            days: 5,
            result: null,
            loading: false,
        });
    }

    async runSimulation() {
        this.state.loading = true;
        try {
            this.state.result = await this.orm.call(MODEL, "run_simulation", [
                this.props.filters,
                this.state.scenario,
                { percent: this.state.percent, days: this.state.days },
            ]);
        } finally {
            this.state.loading = false;
        }
    }

    fmt(v) {
        return formatMonetary(v || 0, { currencyId: this.props.currencyId });
    }

    onCloseClick() {
        if (this.props.onClose) this.props.onClose();
    }
}
