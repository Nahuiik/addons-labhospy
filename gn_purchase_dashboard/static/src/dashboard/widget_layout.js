/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

/** Layout por defecto estilo Power BI (grid 12 columnas). */
export const DEFAULT_WIDGET_LAYOUT = [
    { id: "monthly_purchases", x: 0, y: 0, w: 4, h: 2, minW: 3, minH: 2 },
    { id: "top_categories", x: 4, y: 0, w: 4, h: 2, minW: 3, minH: 2 },
    { id: "purchases_by_company", x: 8, y: 0, w: 4, h: 2, minW: 3, minH: 2 },
    { id: "sankey_flow", x: 0, y: 2, w: 6, h: 3, minW: 4, minH: 2 },
    { id: "waterfall_financial", x: 6, y: 2, w: 6, h: 3, minW: 4, minH: 2 },
    { id: "top_vendors", x: 0, y: 5, w: 12, h: 3, minW: 6, minH: 2 },
    { id: "heatmap", x: 0, y: 8, w: 6, h: 3, minW: 4, minH: 2 },
    { id: "price_variation", x: 6, y: 8, w: 6, h: 3, minW: 4, minH: 2 },
    { id: "lead_time", x: 0, y: 11, w: 6, h: 2, minW: 3, minH: 2 },
    { id: "lead_histogram", x: 6, y: 11, w: 6, h: 2, minW: 3, minH: 2 },
    { id: "kanban_summary", x: 0, y: 13, w: 12, h: 3, minW: 6, minH: 2 },
    { id: "receipts", x: 0, y: 16, w: 6, h: 2, minW: 3, minH: 2 },
    { id: "forecast", x: 6, y: 16, w: 6, h: 2, minW: 3, minH: 2 },
    { id: "abc_analysis", x: 0, y: 18, w: 6, h: 3, minW: 4, minH: 2 },
    { id: "concentration", x: 6, y: 18, w: 6, h: 3, minW: 4, minH: 2 },
    { id: "financial", x: 0, y: 21, w: 6, h: 2, minW: 3, minH: 2 },
    { id: "buyers", x: 6, y: 21, w: 6, h: 3, minW: 4, minH: 2 },
    { id: "products", x: 0, y: 24, w: 12, h: 3, minW: 6, minH: 2 },
    { id: "drilldown", x: 0, y: 27, w: 12, h: 1, minW: 4, minH: 1 },
];

export const WIDGET_META = {
    monthly_purchases: { icon: "fa-line-chart", desc: "Evolución del gasto por mes" },
    top_categories: { icon: "fa-pie-chart", desc: "Distribución por categoría" },
    purchases_by_company: { icon: "fa-building-o", desc: "Compras por entidad" },
    sankey_flow: { icon: "fa-random", desc: "Flujo categoría → proveedor" },
    waterfall_financial: { icon: "fa-bar-chart", desc: "Ciclo financiero de compras" },
    top_vendors: { icon: "fa-truck", desc: "Ranking de proveedores" },
    heatmap: { icon: "fa-th", desc: "Intensidad por dimensión" },
    price_variation: { icon: "fa-tag", desc: "Variación de precios" },
    lead_time: { icon: "fa-clock-o", desc: "Tiempo de entrega promedio" },
    lead_histogram: { icon: "fa-area-chart", desc: "Distribución de lead times" },
    kanban_summary: { icon: "fa-columns", desc: "Estado operativo de OC" },
    receipts: { icon: "fa-inbox", desc: "Cumplimiento de recepciones" },
    forecast: { icon: "fa-forward", desc: "Proyección de compras" },
    abc_analysis: { icon: "fa-sort-amount-desc", desc: "Análisis ABC / Pareto" },
    concentration: { icon: "fa-compress", desc: "Concentración de gasto" },
    financial: { icon: "fa-money", desc: "Comprometido vs facturado" },
    buyers: { icon: "fa-user", desc: "Desempeño por comprador" },
    products: { icon: "fa-cube", desc: "Top productos comprados" },
    drilldown: { icon: "fa-sitemap", desc: "Enlaces de navegación" },
};

export const WIDGET_LABELS = {
    monthly_purchases: () => _t("Compras por mes"),
    top_categories: () => _t("Top categorías"),
    purchases_by_company: () => _t("Compras por empresa"),
    sankey_flow: () => _t("Flujo Sankey"),
    waterfall_financial: () => _t("Waterfall financiero"),
    top_vendors: () => _t("Top proveedores"),
    heatmap: () => _t("Mapa de calor"),
    price_variation: () => _t("Variación de precios"),
    lead_time: () => _t("Lead Time"),
    lead_histogram: () => _t("Distribución lead time"),
    kanban_summary: () => _t("Órdenes de compra"),
    receipts: () => _t("Recepciones"),
    forecast: () => _t("Forecast"),
    abc_analysis: () => _t("Análisis ABC"),
    concentration: () => _t("Concentración"),
    financial: () => _t("Dashboard financiero"),
    buyers: () => _t("Compras por comprador"),
    products: () => _t("Productos"),
    drilldown: () => _t("Drill-down"),
};

export function mergeLayout(savedWidgets, savedMeta = {}) {
    const byId = Object.fromEntries((savedWidgets || []).map((w) => [w.id, w]));
    const hidden = new Set(savedMeta.hidden || []);
    const pinned = new Set(savedMeta.pinned || []);
    const favorites = new Set(savedMeta.favorites || []);
    return DEFAULT_WIDGET_LAYOUT.map((def) => {
        const saved = byId[def.id];
        const item = saved ? {
            ...def,
            x: saved.x ?? def.x,
            y: saved.y ?? def.y,
            w: Math.max(saved.w ?? def.w, def.minW || 2),
            h: Math.max(saved.h ?? def.h, def.minH || 1),
        } : { ...def };
        item.hidden = hidden.has(item.id);
        item.pinned = pinned.has(item.id);
        item.favorite = favorites.has(item.id);
        return item;
    }).sort((a, b) => a.y - b.y || a.x - b.x);
}

export function visibleLayout(layout) {
    return layout.filter((item) => !item.hidden);
}

export function layoutMetaPayload(layout) {
    return {
        hidden: layout.filter((i) => i.hidden).map((i) => i.id),
        pinned: layout.filter((i) => i.pinned).map((i) => i.id),
        favorites: layout.filter((i) => i.favorite).map((i) => i.id),
    };
}

export function toggleLayoutFlag(layout, id, flag) {
    return layout.map((item) => item.id === id ? { ...item, [flag]: !item[flag] } : item);
}

export function gridItemStyle(item) {
    return `grid-column: ${item.x + 1} / span ${item.w}; grid-row: ${item.y + 1} / span ${item.h};`;
}

export function swapLayoutItems(layout, idA, idB) {
    const copy = layout.map((i) => ({ ...i }));
    const a = copy.find((i) => i.id === idA);
    const b = copy.find((i) => i.id === idB);
    if (!a || !b) return copy;
    [a.x, b.x] = [b.x, a.x];
    [a.y, b.y] = [b.y, a.y];
    [a.w, b.w] = [b.w, a.w];
    [a.h, b.h] = [b.h, a.h];
    return copy.sort((x, y) => x.y - y.y || x.x - x.x);
}

export function resizeLayoutItem(layout, id, deltaW, deltaH) {
    return layout.map((item) => {
        if (item.id !== id) return item;
        const w = Math.min(12 - item.x, Math.max(item.minW || 2, item.w + deltaW));
        const h = Math.max(item.minH || 1, item.h + deltaH);
        return { ...item, w, h };
    });
}

export function layoutToPayload(layout) {
    return layout.map(({ id, x, y, w, h }) => ({ id, x, y, w, h }));
}
