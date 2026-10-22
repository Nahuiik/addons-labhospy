/** @odoo-module **/

import { loadBundle } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import { onMounted, onWillUnmount, useEffect, useRef } from "@odoo/owl";

export const CHART_COLORS = {
    inflow: "rgba(25, 135, 84, 0.82)",
    inflowBorder: "rgba(25, 135, 84, 1)",
    inflowMuted: "rgba(25, 135, 84, 0.35)",
    outflow: "rgba(220, 53, 69, 0.82)",
    outflowBorder: "rgba(220, 53, 69, 1)",
    outflowMuted: "rgba(220, 53, 69, 0.35)",
    net: "rgba(51, 65, 85, 0.9)",
    netBorder: "rgba(51, 65, 85, 1)",
    netNegative: "rgba(220, 53, 69, 1)",
    balance: "rgba(13, 110, 253, 0.15)",
    balanceBorder: "rgba(13, 110, 253, 1)",
    balanceLine: "rgba(13, 110, 253, 0.85)",
    closingLine: "rgba(91, 44, 111, 0.85)",
    averageLine: "rgba(108, 117, 125, 0.7)",
    total: "rgba(108, 117, 125, 0.85)",
    totalMuted: "rgba(108, 117, 125, 0.55)",
    subtotal: "rgba(13, 110, 253, 0.75)",
    highlight: "rgba(255, 193, 7, 0.35)",
    brand: "rgba(91, 44, 111, 0.85)",
};

export async function loadChartJs() {
    if (typeof Chart !== "undefined") {
        return;
    }
    if (!loadChartJs._promise) {
        loadChartJs._promise = loadBundle("web.chartjs_lib");
    }
    await loadChartJs._promise;
}

export function destroyChart(chart) {
    if (chart) {
        chart.destroy();
    }
    return null;
}

export function baseChartOptions(extra = {}) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { position: "top", labels: { boxWidth: 12, font: { size: 11 } } } },
        ...extra,
    };
}

export function formatChartMoney(value, symbol = "$") {
    const n = Number(value ?? 0);
    return `${symbol}${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** Plugin: connector lines between floating waterfall bars. */
export const waterfallConnectorPlugin = {
    id: "waterfallConnectors",
    afterDatasetsDraw(chart) {
        const { ctx, data, chartArea } = chart;
        const meta = chart.getDatasetMeta(1);
        if (!meta?.data?.length) {
            return;
        }
        ctx.save();
        ctx.strokeStyle = "rgba(108, 117, 125, 0.45)";
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);
        for (let i = 0; i < meta.data.length - 1; i++) {
            const bar = meta.data[i];
            const next = meta.data[i + 1];
            if (!bar || !next) {
                continue;
            }
            const baseY = bar.y + (bar.height || 0);
            ctx.beginPath();
            ctx.moveTo(bar.x, baseY);
            ctx.lineTo(next.x, baseY);
            ctx.stroke();
        }
        ctx.restore();
        void chartArea;
        void data;
    },
};

export function attachWeekHover(chart, weekKeys, sync) {
    if (!chart?.canvas || !sync) {
        return;
    }
    chart.canvas.onmousemove = (ev) => {
        const pts = chart.getElementsAtEventForMode(ev, "index", { intersect: false }, false);
        if (pts.length) {
            const idx = pts[0].index;
            sync.setHighlightedWeek(weekKeys[idx] || null);
        }
    };
    chart.canvas.onmouseleave = () => sync.clear();
}

export function weekHighlightPlugin(highlightRef, weekKeys) {
    return {
        id: "weekHighlight",
        beforeDatasetsDraw(chart) {
            const highlightKey = highlightRef?.key;
            if (!highlightKey || !weekKeys?.length) {
                return;
            }
            const idx = weekKeys.indexOf(highlightKey);
            if (idx < 0) {
                return;
            }
            const xScale = chart.scales.x;
            if (!xScale) {
                return;
            }
            const ctx = chart.ctx;
            const left = xScale.getPixelForValue(idx) - xScale.width / weekKeys.length / 2;
            const width = xScale.width / weekKeys.length;
            ctx.save();
            ctx.fillStyle = CHART_COLORS.highlight;
            ctx.fillRect(left, chart.chartArea.top, width, chart.chartArea.bottom - chart.chartArea.top);
            ctx.restore();
        },
    };
}

export function axisShortLabels(maxRotation = 0) {
    return {
        ticks: { maxRotation, minRotation: 0, autoSkip: true, font: { size: 10 } },
    };
}

/**
 * Lifecycle hook shared by weekly chart components (cashflow, balance
 * evolution). Owns the canvas ref, Chart.js instance, week-sync subscription
 * and re-render fingerprint.
 *
 * The owning component must define:
 *   - this.canvasRef (set by this hook to a useRef("canvas")).
 *   - this.chart (managed here; null when not initialized).
 *   - async renderChart(): builds or updates the chart in place.
 *
 * NOTE: only ``useEffect`` triggers ``renderChart``. Calling it from both
 * ``onMounted`` and ``useEffect`` led to two concurrent ``loadChartJs`` /
 * ``new Chart(...)`` paths racing each other on the first paint, which the
 * user saw as constant flickering. ``useEffect`` already runs after the
 * initial mount, so a single entry point is enough; ``onMounted`` only sets
 * up the week-sync subscription.
 *
 * @param {Component} component
 * @param {Object}    options
 * @param {Function}  options.fingerprint  Returns a string used as useEffect dep.
 */
export function useWeeklyChart(component, { fingerprint }) {
    component.canvasRef = useRef("canvas");
    component.chart = null;
    component._unsub = null;
    component.highlightRef = { key: null };
    component._renderInFlight = false;
    component._renderPending = false;

    const safeRender = async () => {
        if (component._renderInFlight) {
            component._renderPending = true;
            return;
        }
        component._renderInFlight = true;
        try {
            await component.renderChart();
        } finally {
            component._renderInFlight = false;
            if (component._renderPending) {
                component._renderPending = false;
                await safeRender();
            }
        }
    };
    component._safeRenderChart = safeRender;

    onMounted(() => {
        if (component.props.weekSync) {
            component._unsub = component.props.weekSync.subscribe((weekKey) => {
                component.highlightRef.key = weekKey || null;
                if (component.chart) {
                    component.chart.update("none");
                }
            });
        }
    });

    useEffect(
        () => {
            safeRender();
        },
        () => [fingerprint()],
    );

    onWillUnmount(() => {
        if (component._unsub) {
            component._unsub();
            component._unsub = null;
        }
        if (component.chart?.canvas) {
            component.chart.canvas.onmousemove = null;
            component.chart.canvas.onmouseleave = null;
        }
        component.chart = destroyChart(component.chart);
    });
}
