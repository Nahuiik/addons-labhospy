/** @odoo-module */

import { ForecastedButtons } from "@stock/stock_forecasted/forecasted_buttons";
import { StockForecasted } from "@stock/stock_forecasted/stock_forecasted";
import { patch } from "@web/core/utils/patch";

patch(ForecastedButtons, {
    props: {
        ...ForecastedButtons.props,
        canUpdateQty: { type: Boolean, optional: true },
    },
});

const _superSetup = StockForecasted.prototype.setup;
const _superGetReportValues = StockForecasted.prototype._getReportValues;

patch(StockForecasted.prototype, {
    setup(...args) {
        if (_superSetup) {
            _superSetup.call(this, ...args);
        }
        this.canUpdateQty = false;
    },
    async _getReportValues(...args) {
        if (_superGetReportValues) {
            await _superGetReportValues.call(this, ...args);
        }
        this.canUpdateQty = !!(this.docs && this.docs.can_update_qty);
    },
});
