/** @odoo-module **/

import { loadBundle } from "@web/core/assets";

let chartPromise = null;

export async function loadChartJs() {
    if (typeof Chart !== "undefined") {
        return Chart;
    }
    if (!chartPromise) {
        chartPromise = loadBundle("web.chartjs_lib");
    }
    await chartPromise;
    return Chart;
}

export function destroyChart(chart) {
    if (chart) {
        chart.destroy();
    }
    return null;
}

/** Destruye cualquier Chart.js registrado en el canvas (p. ej. tras cambiar pestaña OWL). */
export function destroyCanvasChart(canvas) {
    if (!canvas || typeof Chart === "undefined") {
        return;
    }
    const existing = Chart.getChart(canvas);
    if (existing) {
        existing.destroy();
    }
}

export function destroyAllCharts(chartsMap) {
    if (!chartsMap) {
        return;
    }
    for (const key of Object.keys(chartsMap)) {
        chartsMap[key] = destroyChart(chartsMap[key]);
    }
}

export const CHART_COLORS = [
    "#2563eb", "#059669", "#d97706", "#dc2626", "#7c3aed",
    "#0891b2", "#be185d", "#4f46e5", "#0d9488", "#ca8a04",
];

export function paletteColors(n) {
    return Array.from({ length: n }, (_, i) => CHART_COLORS[i % CHART_COLORS.length]);
}

export function baseChartOptions(type = "bar") {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: type !== "bar", position: "bottom" },
            tooltip: { mode: "index", intersect: false },
        },
        scales: type === "bar" || type === "line" ? {
            x: { grid: { display: false } },
            y: { beginAtZero: true, grid: { color: "rgba(0,0,0,0.06)" } },
        } : {},
    };
}

export function buildChartConfig(chartDef) {
    const typeMap = {
        horizontal_bar: "bar",
        stacked_bar: "bar",
        treemap: "bar",
        gauge: "doughnut",
        pareto: "bar",
        heatmap: "bar",
    };
    const chartType = typeMap[chartDef.type] || chartDef.type || "bar";
    const options = baseChartOptions(chartType);
    if (chartDef.type === "horizontal_bar") {
        options.indexAxis = "y";
    }
    if (chartDef.type === "stacked_bar") {
        options.scales = {
            x: { stacked: true, grid: { display: false } },
            y: { stacked: true, beginAtZero: true },
        };
    }
    if (chartDef.type === "gauge") {
        const val = chartDef.value || 0;
        return {
            type: "doughnut",
            data: {
                labels: ["Score", "Rest"],
                datasets: [{
                    data: [val, Math.max(0, 100 - val)],
                    backgroundColor: [
                        val >= 75 ? "#059669" : val >= 50 ? "#d97706" : "#dc2626",
                        "#e5e7eb",
                    ],
                    borderWidth: 0,
                }],
            },
            options: {
                ...options,
                cutout: "75%",
                plugins: { legend: { display: false } },
            },
        };
    }
    if (chartDef.type === "waterfall") {
        const vals = chartDef.values || [];
        const colors = vals.map((v) => (v >= 0 ? "#059669" : "#dc2626"));
        return {
            type: "bar",
            data: {
                labels: chartDef.labels || [],
                datasets: [{
                    data: vals.map((v) => Math.abs(v)),
                    backgroundColor: colors,
                    borderRadius: 6,
                }],
            },
            options,
        };
    }
    if (chartDef.type === "heatmap" && chartDef.matrix) {
        const datasets = (chartDef.matrix || []).map((row, idx) => ({
            label: `S${idx + 1}`,
            data: row,
            backgroundColor: paletteColors(1)[0],
            borderRadius: 4,
        }));
        options.scales = {
            x: { stacked: false, grid: { display: false } },
            y: { beginAtZero: true, grid: { color: "rgba(0,0,0,0.06)" } },
        };
        return { type: "bar", data: { labels: chartDef.labels || [], datasets }, options };
    }
    if (chartDef.type === "line") {
        return {
            type: "line",
            data: {
                labels: chartDef.labels || [],
                datasets: [{
                    data: chartDef.values || [],
                    borderColor: "#2563eb",
                    backgroundColor: "rgba(37,99,235,0.15)",
                    fill: true,
                    tension: 0.35,
                }],
            },
            options,
        };
    }
    if (chartDef.datasets) {
        return {
            type: chartType,
            data: {
                labels: chartDef.labels || [],
                datasets: chartDef.datasets.map((ds, i) => ({
                    ...ds,
                    backgroundColor: paletteColors(ds.data?.length || 1),
                    borderRadius: 6,
                })),
            },
            options,
        };
    }
    return {
        type: chartType,
        data: {
            labels: chartDef.labels || [],
            datasets: [{
                label: chartDef.label || "",
                data: chartDef.values || [],
                backgroundColor: paletteColors((chartDef.values || []).length),
                borderRadius: 6,
            }],
        },
        options,
    };
}
