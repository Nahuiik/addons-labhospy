/** @odoo-module **/

export function kpiVariationClass(kpi) {
    if (!kpi?.has_data || kpi?.empty_reason) {
        return "gn-pd-kpi__var--neutral";
    }
    const tone = kpi.semantic_tone || "neutral";
    return {
        success: "gn-pd-kpi__var--success",
        danger: "gn-pd-kpi__var--danger",
        neutral: "gn-pd-kpi__var--neutral",
    }[tone] || "gn-pd-kpi__var--neutral";
}

export function kpiPrimaryKeys() {
    return new Set([
        "total_purchased", "po_count", "pending_approval",
        "pending_receive", "pending_invoice", "pending_amount",
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
        buyer_id: filterOptions.buyers,
        vendor_id: filterOptions.vendors,
        warehouse_id: filterOptions.warehouses,
        category_id: filterOptions.categories,
        company_id: filterOptions.companies,
        project_id: filterOptions.projects,
        tag_id: filterOptions.tags,
        po_state: filterOptions.po_states,
        compare_mode: filterOptions.compare_modes,
        period: filterOptions.period_presets,
    };
    const prefix = {
        branch_id: labels.branch,
        buyer_id: labels.buyer,
        vendor_id: labels.vendor,
        company_id: "Compañía",
        warehouse_id: labels.warehouse || "Almacén",
        category_id: labels.category || "Categoría",
        compare_mode: labels.compare || "Comparación",
        period: labels.period || "Período",
        po_state: labels.poState || "Estado",
        project_id: "Proyecto",
        tag_id: "Etiqueta",
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
