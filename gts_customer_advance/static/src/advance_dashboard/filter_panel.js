/** @odoo-module **/

import { Component } from "@odoo/owl";

export class FilterPanel extends Component {
    static template = "gts_customer_advance.FilterPanel";
    static props = {
        filters: Object,
        filterOptions: Object,
        onFiltersChanged: Function,
    };

    get periods() {
        return [
            { id: "today", name: "Hoy" },
            { id: "this_week", name: "Esta Semana" },
            { id: "this_month", name: "Este Mes" },
            { id: "this_quarter", name: "Este Trimestre" },
            { id: "this_year", name: "Este Año" },
            { id: "custom", name: "Rango Personalizado" },
        ];
    }

    get creators() {
        return [
            { id: "all", name: "Todos" },
            ...(this.props.filterOptions.creators || []),
        ];
    }

    onPeriodChange(ev) {
        this.props.onFiltersChanged({ period: ev.target.value });
    }

    onDateFromChange(ev) {
        this.props.onFiltersChanged({ date_from: ev.target.value, period: "custom" });
    }

    onDateToChange(ev) {
        this.props.onFiltersChanged({ date_to: ev.target.value, period: "custom" });
    }

    onCreatorChange(ev) {
        const val = ev.target.value;
        this.props.onFiltersChanged({
            creator_id: val === "all" || val === "" ? false : parseInt(val, 10),
        });
    }
}
