/** @odoo-module **/

let echartsPromise = null;

export async function loadEcharts() {
    if (typeof echarts !== "undefined") {
        return echarts;
    }
    if (!echartsPromise) {
        const { loadJS } = await import("@web/core/assets");
        echartsPromise = loadJS("/gn_sales_dashboard/static/lib/echarts.min.js");
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

export function exportEchartPng(instance, filename = "sales-chart.png") {
    if (!instance) return;
    const url = instance.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" });
    const link = document.createElement("a");
    link.download = filename;
    link.href = url;
    link.click();
}

export function aggregateHeroChart(config, groupBy = "day") {
    if (!config?.labels?.length || groupBy === "day") {
        return config;
    }
    const buckets = new Map();
    const labels = config.labels || [];
    const seriesKeys = (config.series || []).map((s) => s.key);
    for (let i = 0; i < labels.length; i++) {
        const raw = labels[i];
        let key = raw;
        if (groupBy === "week") {
            key = raw.slice(0, 7) + "-S" + Math.ceil(parseInt(raw.slice(8, 10) || 1, 10) / 7);
        } else if (groupBy === "month") {
            key = raw.slice(0, 7);
        }
        if (!buckets.has(key)) {
            buckets.set(key, { label: key, sums: {} });
        }
        const b = buckets.get(key);
        for (const s of config.series || []) {
            b.sums[s.key] = (b.sums[s.key] || 0) + (s.data?.[i] || 0);
        }
    }
    const outLabels = [...buckets.keys()];
    const outSeries = (config.series || []).map((s) => ({
        ...s,
        data: outLabels.map((k) => buckets.get(k).sums[s.key] || 0),
    }));
    return { ...config, labels: outLabels, series: outSeries };
}

export function buildHeroChartOption(config, darkMode = false) {
    const textColor = darkMode ? "#94A3B8" : "#697386";
    const axisColor = darkMode ? "rgba(148,163,184,0.2)" : "#e5eaf1";
    const series = (config.series || []).map((s) => ({
        name: s.name,
        type: s.type === "area" ? "line" : (s.type || "line"),
        smooth: true,
        showSymbol: false,
        symbolSize: 6,
        emphasis: { focus: "series", scale: true },
        areaStyle: s.key === "current" ? { opacity: darkMode ? 0.12 : 0.06 } : undefined,
        lineStyle: {
            width: s.key === "current" ? 2.5 : 1.75,
            type: s.key === "target" || s.key === "forecast" ? "dashed" : "solid",
        },
        data: s.data || [],
        z: s.key === "current" ? 3 : 1,
    }));
    return {
        backgroundColor: "transparent",
        tooltip: {
            trigger: "axis",
            axisPointer: { type: "cross" },
            confine: true,
        },
        legend: { top: 0, textStyle: { color: textColor, fontSize: 12 }, type: "scroll" },
        grid: { left: 12, right: 16, top: 44, bottom: 56, containLabel: true },
        xAxis: {
            type: "category",
            boundaryGap: false,
            data: config.labels || [],
            axisLine: { lineStyle: { color: axisColor } },
            axisLabel: { color: textColor, rotate: (config.labels || []).length > 20 ? 45 : 0 },
        },
        yAxis: {
            type: "value",
            axisLine: { show: false },
            splitLine: { lineStyle: { color: axisColor } },
            axisLabel: { color: textColor },
        },
        dataZoom: [
            {
                type: "inside",
                zoomOnMouseWheel: false,
                moveOnMouseWheel: false,
                moveOnMouseMove: true,
            },
            { type: "slider", height: 18, bottom: 4 },
        ],
        series,
        color: darkMode
            ? ["#2563eb", "#94a3b8", "#16a34a", "#0284c7"]
            : ["#2563eb", "#697386", "#16a34a", "#0284c7"],
    };
}
