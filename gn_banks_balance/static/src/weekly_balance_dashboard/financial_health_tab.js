/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import {
    FinancialHealthHeader,
    LiquidityScoreBreakdown,
    CashRunwayCard,
    CashForecastPanel,
    ProjectedTrajectoryChart,
    FinancialRatiosGrid,
    LiquidityTrendCard,
    BankConcentrationPanel,
    HistoricalComparisonPanel,
    SmartAlertsPanel,
    RecommendationsPanel,
    FinancialTimeline,
    FinancialHealthSkeleton,
    FinancialHealthEmptyState,
    FinancialHealthErrorState,
} from "./financial_health_components";
import { IndicatorGaugesPanel } from "./indicator_gauges";

const SUB_TABS = [
    { id: "summary", label: "Resumen" },
    { id: "indicators", label: "Indicadores" },
    { id: "forecast", label: "Forecast y riesgo" },
    { id: "ratios", label: "Ratios" },
    { id: "banks", label: "Bancos" },
    { id: "events", label: "Eventos" },
];

export class FinancialHealthTab extends Component {
    static template = "gn_banks_balance.FinancialHealthTab";
    static components = {
        FinancialHealthHeader,
        LiquidityScoreBreakdown,
        CashRunwayCard,
        CashForecastPanel,
        ProjectedTrajectoryChart,
        FinancialRatiosGrid,
        LiquidityTrendCard,
        BankConcentrationPanel,
        HistoricalComparisonPanel,
        SmartAlertsPanel,
        RecommendationsPanel,
        FinancialTimeline,
        FinancialHealthSkeleton,
        FinancialHealthEmptyState,
        FinancialHealthErrorState,
        IndicatorGaugesPanel,
    };
    static props = {
        loading: Boolean,
        loadError: { type: String, optional: true },
        data: { type: Object, optional: true },
        currencyId: { type: Number, optional: true },
        currencySymbol: { type: String, optional: true },
        onRetry: Function,
    };

    setup() {
        this.state = useState({ subTab: "summary" });
        this.subTabs = SUB_TABS;
    }

    get hasData() {
        return this.props.data?.has_data;
    }

    setSubTab(tab) {
        this.state.subTab = tab;
    }
}
