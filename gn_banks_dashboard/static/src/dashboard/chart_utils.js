/** @odoo-module **/

import { loadBundle } from "@web/core/assets";

/** Executive finance palette (Stripe / Dynamics inspired). */
export const CHART_COLORS = {
    inflow: "rgba(16, 185, 129, 0.72)",
    inflowBorder: "rgba(5, 150, 105, 0.95)",
    inflowFill: "rgba(16, 185, 129, 0.12)",
    outflow: "rgba(239, 68, 68, 0.72)",
    outflowBorder: "rgba(220, 38, 38, 0.95)",
    outflowFill: "rgba(239, 68, 68, 0.08)",
    cumulative: "rgba(99, 102, 241, 0.9)",
    cumulativeFill: "rgba(99, 102, 241, 0.06)",
    trend: "rgba(148, 163, 184, 0.95)",
    grid: "rgba(148, 163, 184, 0.18)",
    tick: "#64748b",
    palette: [
        "#5b2c6f",
        "#6366f1",
        "#0ea5e9",
        "#10b981",
        "#f59e0b",
        "#ef4444",
        "#8b5cf6",
        "#14b8a6",
        "#64748b",
        "#ec4899",
    ],
};

let chartJsLoadPromise = null;

export async function loadChartJs() {
    if (typeof Chart !== "undefined") {
        return;
    }
    if (!chartJsLoadPromise) {
        chartJsLoadPromise = loadBundle("web.chartjs_lib");
    }
    await chartJsLoadPromise;
}

export function destroyChart(chart) {
    if (chart) {
        chart.destroy();
    }
    return null;
}

/**
 * Chart.js defaults tuned for executive dashboards (low noise, high legibility).
 */
export function baseChartOptions(extra = {}) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
            duration: 480,
            easing: "easeOutQuart",
        },
        animations: {
            colors: { duration: 320 },
            y: { duration: 480, easing: "easeOutCubic" },
        },
        interaction: { mode: "nearest", intersect: false, axis: "x" },
        plugins: {
            legend: {
                position: "top",
                align: "end",
                labels: {
                    boxWidth: 8,
                    boxHeight: 8,
                    usePointStyle: true,
                    pointStyle: "circle",
                    padding: 18,
                    font: { size: 12, weight: "500", family: "Inter, system-ui, sans-serif" },
                    color: "#475569",
                },
            },
            tooltip: {
                backgroundColor: "rgba(15, 23, 42, 0.96)",
                titleColor: "#f8fafc",
                titleFont: { size: 12, weight: "700", family: "Inter, system-ui, sans-serif" },
                bodyColor: "#e2e8f0",
                bodyFont: { size: 12, family: "Inter, system-ui, sans-serif" },
                padding: { top: 10, right: 14, bottom: 10, left: 14 },
                cornerRadius: 8,
                boxPadding: 6,
                usePointStyle: true,
                displayColors: true,
                borderColor: "rgba(99, 102, 241, 0.35)",
                borderWidth: 1,
                caretSize: 6,
                caretPadding: 8,
            },
        },
        scales: {
            x: {
                grid: { display: false, drawTicks: false },
                ticks: {
                    color: CHART_COLORS.tick,
                    font: { size: 11, family: "Inter, system-ui, sans-serif" },
                    maxRotation: 0,
                    padding: 6,
                },
                border: { display: false },
            },
            y: {
                grid: { color: CHART_COLORS.grid, drawBorder: false, drawTicks: false },
                ticks: {
                    color: CHART_COLORS.tick,
                    font: { size: 11, family: "Inter, system-ui, sans-serif" },
                    padding: 8,
                },
                border: { display: false },
            },
        },
        ...extra,
    };
}

export function paletteColors(n) {
    const out = [];
    for (let i = 0; i < n; i++) {
        out.push(CHART_COLORS.palette[i % CHART_COLORS.palette.length]);
    }
    return out;
}

export function attachChartDrilldown(chart, onSelect) {
    if (!chart?.options?.plugins) {
        return;
    }
    chart.options.onClick = (_ev, elements) => {
        if (!elements?.length || !onSelect) {
            return;
        }
        const idx = elements[0].index;
        onSelect(idx, chart.data.labels?.[idx]);
    };
    chart.options.onHover = (ev, elements) => {
        const target = ev?.native?.target;
        if (target) {
            target.style.cursor = elements?.length ? "pointer" : "default";
        }
    };
    chart.update("none");
}
