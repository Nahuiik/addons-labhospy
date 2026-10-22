/** @odoo-module **/

import { Component } from "@odoo/owl";
import { BanksWeeklyBalanceKpiCard } from "./kpi_card";

export class KpiCards extends Component {
    static template = "gn_banks_balance.KpiCards";
    static components = { BanksWeeklyBalanceKpiCard };
    static props = {
        primaryCards: Array,
        secondaryCards: Array,
    };
}
