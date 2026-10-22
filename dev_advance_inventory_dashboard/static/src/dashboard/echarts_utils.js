/** @odoo-module **/

import { loadJS } from "@web/core/assets";

let echartsPromise = null;

export async function loadEcharts() {
    if (typeof echarts !== "undefined") {
        return echarts;
    }
    if (!echartsPromise) {
        echartsPromise = loadJS("/dev_advance_inventory_dashboard/static/lib/echarts.min.js");
    }
    await echartsPromise;
    return echarts;
}

export function disposeEchart(instance) {
    if (instance) {
        instance.dispose();
    }
    return null;
}

export function exportEchartPng(instance, filename = "chart.png") {
    if (!instance) return;
    const url = instance.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" });
    const link = document.createElement("a");
    link.download = filename;
    link.href = url;
    link.click();
}

/** Aplica tema claro/oscuro básico a opciones ECharts. */
export function applyEchartsTheme(option, darkMode = false) {
    if (!darkMode || !option) return option;
    const themed = { ...option, backgroundColor: "transparent" };
    if (themed.title) {
        themed.title = { ...themed.title, textStyle: { color: "#f1f5f9" } };
    }
    return themed;
}
