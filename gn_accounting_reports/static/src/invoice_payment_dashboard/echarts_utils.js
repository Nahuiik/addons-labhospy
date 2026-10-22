/** @odoo-module **/

let echartsPromise = null;

export async function loadEcharts() {
    if (typeof echarts !== "undefined") {
        return echarts;
    }
    if (!echartsPromise) {
        const { loadJS } = await import("@web/core/assets");
        echartsPromise = loadJS("/gn_accounting_reports/static/lib/echarts.min.js");
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

export function formatAxisMoney(value, currencySymbol = "L ") {
    const n = Number(value) || 0;
    const sym = currencySymbol.endsWith(" ") ? currencySymbol : `${currencySymbol} `;
    if (Math.abs(n) >= 1_000_000) {
        return `${sym}${(n / 1_000_000).toFixed(1)} M`;
    }
    if (Math.abs(n) >= 1_000) {
        return `${sym}${(n / 1_000).toFixed(0)} mil`;
    }
    return `${sym}${n.toFixed(0)}`;
}

export function buildTimelineOption(config, currencySymbol = "") {
    return {
        tooltip: { trigger: "axis" },
        legend: { bottom: 0 },
        grid: { left: 56, right: 24, top: 24, bottom: 48 },
        xAxis: { type: "category", data: config.labels || [] },
        yAxis: {
            type: "value",
            axisLabel: { formatter: (v) => formatAxisMoney(v, currencySymbol) },
        },
        series: (config.series || []).map((s, i) => ({
            name: s.name,
            type: "line",
            smooth: true,
            data: s.data || [],
            areaStyle: i === 0 ? { opacity: 0.08 } : undefined,
        })),
    };
}

export function buildBarOption(labels, data, horizontal = false, options = {}) {
    const {
        currencySymbol = "",
        fullLabels = [],
        isPct = false,
        showEndLabels = false,
        leftMargin = 180,
    } = options;
    const fmt = (v) => isPct ? `${Number(v).toFixed(1)}%` : formatAxisMoney(v, currencySymbol);
    const truncateEnd = (s, max = 28) => {
        if (!s || s.length <= max) return s;
        return `${s.slice(0, max - 1)}…`;
    };
    const displayLabels = (fullLabels.length ? fullLabels : labels).map((l) => truncateEnd(l));
    return {
        tooltip: {
            trigger: "axis",
            axisPointer: { type: "shadow" },
            formatter: (params) => {
                const p = params[0];
                const full = (fullLabels[p.dataIndex] || p.name);
                return `${full}<br/>${fmt(p.value)}`;
            },
        },
        grid: {
            left: horizontal ? leftMargin : 48,
            right: horizontal ? (showEndLabels ? 72 : 24) : 24,
            top: 16,
            bottom: horizontal ? 16 : 72,
            containLabel: !horizontal,
        },
        xAxis: horizontal
            ? {
                type: "value",
                axisLabel: { formatter: (v) => fmt(v) },
            }
            : {
                type: "category",
                data: displayLabels,
                axisLabel: { rotate: 35, interval: 0, fontSize: 11 },
            },
        yAxis: horizontal
            ? {
                type: "category",
                data: displayLabels,
                axisLabel: {
                    width: leftMargin - 24,
                    overflow: "truncate",
                    fontSize: 11,
                },
            }
            : { type: "value", axisLabel: { formatter: (v) => fmt(v) } },
        series: [{
            type: "bar",
            data,
            label: showEndLabels ? {
                show: true,
                position: "right",
                formatter: (p) => fmt(p.value),
                fontSize: 11,
            } : undefined,
            itemStyle: { borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0] },
        }],
    };
}

export function buildPieOption(labels, data, options = {}) {
    const { currencySymbol = "", percentages = [], formatValue = null } = options;
    const total = data.reduce((a, b) => a + (Number(b) || 0), 0) || 1;
    const fmt = formatValue || ((v) => formatAxisMoney(v, currencySymbol));
    const items = labels.map((l, i) => ({
        name: l,
        value: data[i] || 0,
        pct: percentages[i] ?? Math.round((data[i] || 0) / total * 1000) / 10,
    }));
    return {
        tooltip: {
            trigger: "item",
            formatter: (p) => `${p.name}<br/>${fmt(p.value)} (${p.data.pct}%)`,
        },
        legend: {
            orient: "vertical",
            right: 8,
            top: "middle",
            type: "scroll",
            height: "80%",
            formatter: (name) => {
                const item = items.find((x) => x.name === name);
                if (!item) return name;
                const short = name.length > 18 ? `${name.slice(0, 17)}…` : name;
                return `${short}  ${fmt(item.value)} (${item.pct}%)`;
            },
            textStyle: { fontSize: 11 },
        },
        series: [{
            type: "pie",
            radius: ["42%", "62%"],
            center: ["32%", "50%"],
            avoidLabelOverlap: true,
            label: { show: false },
            labelLine: { show: false },
            data: items,
            emphasis: { itemStyle: { shadowBlur: 8 } },
        }],
    };
}

export function buildGaugeOption(value, thresholds) {
    const good = thresholds?.recovery_good ?? 85;
    const warn = thresholds?.recovery_warn ?? 65;
    let progressColor = "#dc2626";
    if (value >= good) {
        progressColor = "#16a34a";
    } else if (value >= warn) {
        progressColor = "#d97706";
    }
    return {
        series: [{
            type: "gauge",
            startAngle: 200,
            endAngle: -20,
            min: 0,
            max: 100,
            progress: {
                show: true,
                width: 14,
                itemStyle: { color: progressColor },
            },
            axisLine: { lineStyle: { width: 14, color: [[1, "#e2e8f0"]] } },
            pointer: { show: false },
            axisTick: { show: false },
            splitLine: { show: false },
            axisLabel: { show: false },
            detail: {
                valueAnimation: true,
                fontSize: 22,
                color: progressColor,
                offsetCenter: [0, "10%"],
                formatter: "{value}%",
            },
            data: [{ value: Math.round(value * 10) / 10 }],
        }],
    };
}

export function exportChartImage(chartInstance, filename = "grafico.png") {
    if (!chartInstance) return;
    const url = chartInstance.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" });
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
}
