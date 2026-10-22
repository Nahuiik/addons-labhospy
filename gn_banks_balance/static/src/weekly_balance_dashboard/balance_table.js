/** @odoo-module **/

import { Component } from "@odoo/owl";
import { formatMonetary } from "@web/views/fields/formatters";
import { _t } from "@web/core/l10n/translation";

export class BanksWeeklyBalanceTable extends Component {
    static template = "gn_banks_balance.BanksWeeklyBalanceTable";
    static props = {
        data: Object,
        currencyId: Number,
        onDrilldown: { type: Function, optional: true },
        onStatementDrilldown: { type: Function, optional: true },
    };

    fmt(amount) {
        return formatMonetary(amount ?? 0, {
            currencyId: this.props.currencyId,
        });
    }

    rowClass(row) {
        return `gn-wb-row--${row.row_type || "opening"}`;
    }

    cellClass(row) {
        if (row.row_type === "inflow") {
            return "gn-wb-cell--inflow";
        }
        if (row.row_type === "outflow") {
            return "gn-wb-cell--outflow";
        }
        return "";
    }

    canDrill(row) {
        return row.row_type === "inflow" || row.row_type === "outflow" || row.row_type === "opening";
    }

    onCellClick(week, col, row) {
        if (!this.canDrill(row) || !this.props.onDrilldown) {
            return;
        }
        this.props.onDrilldown({
            week_no: week.week_no,
            journal_id: col.journal_id,
            row_type: row.row_type,
        });
    }

    onCellContextMenu(ev, week, col, row) {
        if (!this.canDrill(row) || !this.props.onStatementDrilldown) {
            return;
        }
        ev.preventDefault();
        this.props.onStatementDrilldown({
            week_no: week.week_no,
            journal_id: col.journal_id,
            row_type: row.row_type,
        });
    }

    deltaClass(delta) {
        if (delta > 0) {
            return "gn-wb-delta--up";
        }
        if (delta < 0) {
            return "gn-wb-delta--down";
        }
        return "";
    }

    tooltipDrill() {
        return _t("Clic: movimientos contables · Clic derecho: extracto bancario");
    }
}
