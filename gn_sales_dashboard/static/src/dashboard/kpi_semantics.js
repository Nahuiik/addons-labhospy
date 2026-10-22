/** @odoo-module **/

/** Semántica centralizada de variación KPI (positivo/negativo según métrica). */

export function kpiVariationClass(kpi) {
    if (!kpi?.has_data || kpi?.empty_reason) {
        return "gn-sd-kpi__var--neutral";
    }
    const tone = kpi.semantic_tone || "neutral";
    return {
        success: "gn-sd-kpi__var--success",
        danger: "gn-sd-kpi__var--danger",
        neutral: "gn-sd-kpi__var--neutral",
    }[tone] || "gn-sd-kpi__var--neutral";
}

export function kpiPrimaryKeys() {
    return new Set([
        "net_sales", "gross_margin", "target_achievement",
        "avg_ticket", "active_customers", "pipeline_open",
    ]);
}

export function splitKpis(kpis) {
    const primary = [];
    const secondary = [];
    for (const k of kpis || []) {
        if (k.tier === "primary" || kpiPrimaryKeys().has(k.key)) {
            primary.push(k);
        } else {
            secondary.push(k);
        }
    }
    const order = [...kpiPrimaryKeys()];
    primary.sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key));
    return { primary, secondary };
}

export function filterChipLabel(field, value, filterOptions, labels) {
    if (!value && value !== 0) return null;
    const maps = {
        branch_id: filterOptions.branches,
        team_id: filterOptions.teams,
        user_id: filterOptions.users,
        journal_id: filterOptions.journals,
        warehouse_id: filterOptions.warehouses,
        category_id: filterOptions.categories,
        channel_id: filterOptions.channels,
        company_id: filterOptions.companies,
        partner_id: null,
        product_id: null,
        order_state: filterOptions.order_states,
        compare_mode: filterOptions.compare_modes,
        period: filterOptions.period_presets,
    };
    const prefix = {
        branch_id: labels.branch,
        team_id: labels.team,
        user_id: labels.salesperson,
        company_id: "Compañía",
        journal_id: labels.journal,
        warehouse_id: labels.warehouse || "Almacén",
        category_id: labels.category || "Categoría",
        channel_id: labels.channel || "Canal",
        compare_mode: labels.compare || "Comparación",
        period: labels.period || "Período",
        order_state: labels.orderState || "Estado pedido",
    }[field] || field;
    const list = maps[field];
    if (list) {
        const found = list.find((x) => x.id === value);
        return `${prefix}: ${found?.name || value}`;
    }
    if (field === "date_from" || field === "date_to") {
        const lbl = field === "date_from" ? "Desde" : "Hasta";
        return `${lbl}: ${value}`;
    }
    return `${prefix}: ${value}`;
}
