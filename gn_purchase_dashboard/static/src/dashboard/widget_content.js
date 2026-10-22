/** @odoo-module **/

import { Component } from "@odoo/owl";
import { PurchaseChartPanel } from "./chart_panel";
import { PurchaseLeadTimePanel } from "./lead_time_panel";
import { PurchaseDataTable } from "./purchase_data_table";

export class PurchaseWidgetContent extends Component {
    static template = "gn_purchase_dashboard.PurchaseWidgetContent";
    static components = { PurchaseChartPanel, PurchaseDataTable, PurchaseLeadTimePanel };
    static props = {
        widgetId: String,
        widgets: Object,
        widgetsLoading: Boolean,
        appliedFilters: Object,
        currencyId: Number,
        heatmapConfig: Object,
        heatmapDimension: String,
        abcTab: String,
        kanbanColumns: Array,
        drilldownChain: Array,
        fmtMoney: Function,
        buildMonthlyOption: Function,
        buildTreemapOption: Function,
        buildCompanyOption: Function,
        buildHeatmapOption: Function,
        buildSankeyOption: Function,
        buildWaterfallOption: Function,
        buildLeadGaugeOption: Function,
        buildLeadHistogramOption: Function,
        buildBoxplotOption: Function,
        buildReceiptsOption: Function,
        buildForecastOption: Function,
        buildAbcParetoOption: Function,
        setHeatmapDimension: Function,
        setAbcTab: Function,
        onPoClick: Function,
        onTableRowClick: Function,
        onDrilldownChain: Function,
        onOpenSidePanel: { type: Function, optional: true },
        onChartClick: { type: Function, optional: true },
        darkMode: { type: Boolean, optional: true },
        leadTimeKpi: { type: Object, optional: true },
        urgentOrdersCount: { type: Number, optional: true },
    };

    priorityLabel(p) {
        return { 3: "Urgente", 2: "Alta", 1: "Normal" }[String(p)] || "";
    }

    vendorInitial(name) {
        return (name || "?").trim().charAt(0).toUpperCase();
    }

    get abcEntityType() {
        return this.props.abcTab === "products" ? "product" : "vendor";
    }
}
