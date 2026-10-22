/** @odoo-module **/

let echartsPromise = null;

export async function loadEcharts() {
    if (typeof echarts !== "undefined") {
        return echarts;
    }
    if (!echartsPromise) {
        const { loadJS } = await import("@web/core/assets");
        echartsPromise = loadJS("/gn_purchase_dashboard/static/lib/echarts.min.js");
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

export function buildBarOption(labels, series, darkMode = false) {
    const textColor = darkMode ? "#94A3B8" : "#64748b";
    const gridColor = darkMode ? "rgba(148,163,184,0.12)" : "rgba(15,23,42,0.06)";
    return {
        animationDuration: 600,
        animationEasing: "cubicOut",
        tooltip: { trigger: "axis", backgroundColor: darkMode ? "#1e293b" : "#fff", borderColor: gridColor },
        legend: { show: (series || []).length > 1, textStyle: { color: textColor, fontSize: 11 }, top: 0 },
        grid: { left: 40, right: 16, top: 32, bottom: 28, containLabel: true },
        xAxis: {
            type: "category", data: labels,
            axisLabel: { color: textColor, fontSize: 10 },
            axisLine: { show: false },
            axisTick: { show: false },
        },
        yAxis: {
            type: "value",
            axisLabel: { color: textColor, fontSize: 10 },
            splitLine: { lineStyle: { color: gridColor, type: "dashed" } },
            axisLine: { show: false },
        },
        series: (series || []).map((s) => ({
            name: s.name,
            type: s.type === "area" ? "line" : (s.type || "bar"),
            stack: s.stack,
            smooth: true,
            showSymbol: false,
            barMaxWidth: 36,
            itemStyle: { borderRadius: s.type === "bar" ? [4, 4, 0, 0] : 0 },
            areaStyle: s.type === "area" ? { opacity: 0.08 } : undefined,
            lineStyle: { type: s.key === "yoy" || s.key === "forecast" ? "dashed" : "solid", width: 2 },
            data: s.data || [],
        })),
    };
}

export function buildTreemapOption(items, darkMode = false) {
    return {
        tooltip: { formatter: "{b}: {c}" },
        series: [{
            type: "treemap",
            roam: false,
            label: { show: true, formatter: "{b}" },
            data: items || [],
        }],
    };
}

export function buildHeatmapOption(data, darkMode = false) {
    const months = [...new Set((data || []).map((d) => d[0]))];
    const vendors = [...new Set((data || []).map((d) => d[1]))];
    const values = (data || []).map((d) => [months.indexOf(d[0]), vendors.indexOf(d[1]), d[2] || 0]);
    const max = Math.max(...values.map((v) => v[2]), 1);
    return {
        tooltip: { position: "top" },
        grid: { height: "70%", top: "10%" },
        xAxis: { type: "category", data: months, splitArea: { show: true } },
        yAxis: { type: "category", data: vendors, splitArea: { show: true } },
        visualMap: { min: 0, max, calculable: true, orient: "horizontal", left: "center", bottom: 0 },
        series: [{ type: "heatmap", data: values, label: { show: false } }],
    };
}

export function buildGaugeOption(value, max = 100, darkMode = false) {
    return {
        series: [{
            type: "gauge",
            min: 0,
            max,
            progress: { show: true, width: 12 },
            axisLine: { lineStyle: { width: 12 } },
            detail: { valueAnimation: true, formatter: "{value}", fontSize: 20 },
            data: [{ value: value || 0 }],
        }],
    };
}

export function buildPieOption(items, darkMode = false) {
    return {
        tooltip: { trigger: "item" },
        series: [{
            type: "pie",
            radius: ["45%", "70%"],
            avoidLabelOverlap: true,
            itemStyle: { borderRadius: 6, borderColor: darkMode ? "#1e293b" : "#fff", borderWidth: 2 },
            label: { show: true },
            data: items || [],
        }],
    };
}

export function buildForecastOption(points, darkMode = false) {
    const labels = (points || []).map((p) => `${p.days}d`);
    return {
        tooltip: { trigger: "axis" },
        legend: { data: ["Proyección", "Conservador", "Optimista"] },
        xAxis: { type: "category", data: labels },
        yAxis: { type: "value" },
        series: [
            { name: "Proyección", type: "line", smooth: true, areaStyle: { opacity: 0.15 }, data: points.map((p) => p.projection) },
            { name: "Conservador", type: "line", smooth: true, lineStyle: { type: "dashed" }, data: points.map((p) => p.conservative) },
            { name: "Optimista", type: "line", smooth: true, lineStyle: { type: "dashed" }, data: points.map((p) => p.optimistic) },
        ],
    };
}

export function buildHistogramOption(values, darkMode = false) {
    if (!values?.length) return {};
    const max = Math.max(...values, 1);
    const bins = 12;
    const step = Math.ceil(max / bins) || 1;
    const buckets = Array(bins).fill(0);
    for (const v of values) {
        const idx = Math.min(bins - 1, Math.floor(v / step));
        buckets[idx] += 1;
    }
    const labels = buckets.map((_, i) => `${i * step}-${(i + 1) * step}`);
    return {
        tooltip: { trigger: "axis" },
        xAxis: { type: "category", data: labels },
        yAxis: { type: "value" },
        series: [{ type: "bar", data: buckets, itemStyle: { borderRadius: [4, 4, 0, 0] } }],
    };
}

export function buildParetoOption(pareto, darkMode = false) {
    if (!pareto?.labels?.length) return {};
    return {
        tooltip: { trigger: "axis" },
        legend: { data: ["Valor", "Acumulado %"] },
        xAxis: { type: "category", data: pareto.labels, axisLabel: { rotate: 35 } },
        yAxis: [{ type: "value" }, { type: "value", max: 100 }],
        series: [
            { name: "Valor", type: "bar", data: pareto.bars },
            { name: "Acumulado %", type: "line", yAxisIndex: 1, smooth: true, data: pareto.line },
        ],
    };
}

export function buildBoxplotOption(items, darkMode = false) {
    const data = (items || []).map((i) => i.value || i.boxplot);
    const labels = (items || []).map((i) => (i.name || "").slice(0, 18));
    return {
        tooltip: { trigger: "item" },
        xAxis: { type: "category", data: labels, axisLabel: { rotate: 35 } },
        yAxis: { type: "value" },
        series: [{ type: "boxplot", data }],
    };
}

export function buildSankeyOption(config, darkMode = false) {
    if (!config?.nodes?.length) return {};
    return {
        tooltip: { trigger: "item" },
        series: [{
            type: "sankey",
            layout: "none",
            emphasis: { focus: "adjacency" },
            nodeAlign: "left",
            lineStyle: { color: "gradient", curveness: 0.5 },
            label: { color: darkMode ? "#e2e8f0" : "#334155", fontSize: 11 },
            data: config.nodes,
            links: config.links || [],
        }],
    };
}

export function buildWaterfallOption(config, darkMode = false) {
    const steps = config?.steps || [];
    if (!steps.length) return {};
    const labels = steps.map((s) => s.name);
    const placeholders = [];
    const values = [];
    const colors = [];
    let cumulative = 0;
    for (const step of steps) {
        const val = step.value || 0;
        if (step.type === "start") {
            placeholders.push(0);
            values.push(val);
            colors.push("#2563eb");
            cumulative = val;
        } else if (step.type === "total") {
            placeholders.push(0);
            values.push(val);
            colors.push("#64748b");
        } else if (val >= 0) {
            placeholders.push(cumulative);
            values.push(val);
            colors.push("#16a34a");
            cumulative += val;
        } else {
            placeholders.push(cumulative + val);
            values.push(-val);
            colors.push("#dc2626");
            cumulative += val;
        }
    }
    return {
        tooltip: {
            trigger: "axis",
            formatter: (params) => {
                const p = params[1] || params[0];
                return `${p.name}: ${p.value}`;
            },
        },
        grid: { left: 48, right: 24, top: 24, bottom: 48 },
        xAxis: { type: "category", data: labels, axisLabel: { rotate: 30, fontSize: 10 } },
        yAxis: { type: "value" },
        series: [
            {
                name: "Placeholder",
                type: "bar",
                stack: "waterfall",
                itemStyle: { borderColor: "transparent", color: "transparent" },
                emphasis: { itemStyle: { borderColor: "transparent", color: "transparent" } },
                data: placeholders,
            },
            {
                name: "Monto",
                type: "bar",
                stack: "waterfall",
                data: values.map((v, i) => ({
                    value: v,
                    itemStyle: { color: colors[i], borderRadius: [4, 4, 0, 0] },
                })),
            },
        ],
    };
}

export function buildRadarOption(dimensions, darkMode = false) {
    const items = dimensions || [];
    const indicators = items.map((d) => ({ name: d.label, max: 100 }));
    const values = items.map((d) => d.value || 0);
    return {
        tooltip: {},
        radar: {
            indicator: indicators,
            splitArea: { areaStyle: { color: darkMode ? ["#1e293b", "#0f172a"] : ["#f8fafc", "#fff"] } },
        },
        series: [{
            type: "radar",
            areaStyle: { opacity: 0.2 },
            data: [{ value: values, name: "Scorecard" }],
        }],
    };
}
