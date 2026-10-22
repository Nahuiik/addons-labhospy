/** @odoo-module **/

import { Component, onMounted, onPatched, onWillUnmount, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { loadEcharts, disposeEchart } from "./echarts_utils";

const COLORS = {
    excellent: "#059669",
    good: "#2563eb",
    acceptable: "#ca8a04",
    regular: "#ea580c",
    critical: "#b91c1c",
};

export function maturityColor(value) {
    const v = Number(value) || 0;
    if (v >= 90) return COLORS.excellent;
    if (v >= 75) return COLORS.good;
    if (v >= 60) return COLORS.acceptable;
    if (v >= 40) return COLORS.regular;
    return COLORS.critical;
}

export function maturityStatus(value) {
    const v = Number(value) || 0;
    if (v >= 90) return { key: "excellent", label: _t("Excelente") };
    if (v >= 75) return { key: "good", label: _t("Bueno") };
    if (v >= 60) return { key: "acceptable", label: _t("Aceptable") };
    if (v >= 40) return { key: "regular", label: _t("Regular") };
    return { key: "critical", label: _t("Crítico") };
}

const TOOLTIP_META = {
    procurement_maturity: {
        calculation: _t("100 menos el impacto de órdenes urgentes en el período."),
        meaning: _t("Refleja la madurez end-to-end del proceso de compras."),
        recommendation: _t("Planificar compras con anticipación para reducir urgencias."),
    },
    supplier_risk: {
        calculation: _t("Combina concentración HHI y alertas de variación de precio."),
        meaning: _t("Evalúa el riesgo agregado de la base de proveedores."),
        recommendation: _t("Diversificar proveedores críticos y monitorear variaciones."),
    },
    negotiation: {
        calculation: _t("Relación entre ahorro generado y compras totales del período."),
        meaning: _t("Mide la capacidad de negociación y generación de ahorro."),
        recommendation: _t("Revisar contratos marco y oportunidades de renegociación."),
    },
    compliance: {
        calculation: _t("Porcentaje de recepciones completadas a tiempo."),
        meaning: _t("Indica el cumplimiento de plazos acordados con proveedores."),
        recommendation: _t("Seguimiento proactivo a recepciones en riesgo de retraso."),
    },
    digital_score: {
        calculation: _t("Índice compuesto de adopción digital del ciclo P2P."),
        meaning: _t("Nivel de digitalización del proceso procure-to-pay."),
        recommendation: _t("Automatizar aprobaciones y flujos repetitivos."),
    },
    automation: {
        calculation: _t("Inverso del peso de aprobaciones manuales pendientes."),
        meaning: _t("Grado de automatización vs intervención manual."),
        recommendation: _t("Reducir cuellos de botella en aprobaciones pendientes."),
    },
};

function buildMaturityGaugeOption(value, darkMode = false) {
    const color = maturityColor(value);
    const track = darkMode ? "rgba(148,163,184,0.12)" : "rgba(15,23,42,0.06)";
    const tick = darkMode ? "rgba(148,163,184,0.2)" : "rgba(100,116,139,0.18)";
    const label = darkMode ? "rgba(148,163,184,0.35)" : "rgba(100,116,139,0.45)";
    return {
        animationDuration: 650,
        animationEasing: "cubicOut",
        series: [{
            type: "gauge",
            startAngle: 180,
            endAngle: 0,
            center: ["50%", "88%"],
            radius: "110%",
            min: 0,
            max: 100,
            splitNumber: 4,
            axisLine: {
                lineStyle: { width: 5, color: [[1, track]] },
            },
            progress: {
                show: true,
                width: 5,
                roundCap: true,
                itemStyle: { color },
            },
            pointer: { show: false },
            axisTick: { show: false },
            splitLine: {
                show: true,
                length: 3,
                distance: -2,
                lineStyle: { width: 1, color: tick },
            },
            axisLabel: {
                show: true,
                distance: 14,
                fontSize: 7,
                color: label,
                formatter: (v) => (v % 25 === 0 ? String(v) : ""),
            },
            detail: { show: false },
            title: { show: false },
            data: [{ value: value || 0 }],
        }],
    };
}

function shortDescription(index) {
    const map = {
        procurement_maturity: _t("Mide el nivel de madurez del proceso."),
        supplier_risk: _t("Evalúa el riesgo de proveedores."),
        negotiation: _t("Capacidad de generar ahorro."),
        compliance: _t("Cumplimiento de recepciones a tiempo."),
        digital_score: _t("Nivel de adopción digital P2P."),
        automation: _t("Nivel de automatización."),
    };
    return index.description || map[index.key] || "";
}

export class MaturityGaugeCard extends Component {
    static template = "gn_purchase_dashboard.MaturityGaugeCard";
    static props = {
        index: Object,
        darkMode: { type: Boolean, optional: true },
    };

    setup() {
        this.chartRef = useRef("gaugeChart");
        this._chart = null;
        this.state = useState({ pulse: false, showTip: false });
        this._prevValue = this.displayValue;
        onMounted(() => this.renderChart());
        onPatched(() => {
            this.renderChart();
            const next = this.displayValue;
            if (next !== this._prevValue) {
                this._prevValue = next;
                this.state.pulse = true;
                setTimeout(() => { this.state.pulse = false; }, 550);
            }
        });
        onWillUnmount(() => {
            this._chart = disposeEchart(this._chart);
        });
    }

    get displayValue() {
        return Math.round((Number(this.props.index?.value) || 0) * 10) / 10;
    }

    get status() {
        return maturityStatus(this.displayValue);
    }

    get color() {
        return maturityColor(this.displayValue);
    }

    get shortDesc() {
        return shortDescription(this.props.index || {});
    }

    get tooltipMeta() {
        const key = this.props.index?.key;
        return TOOLTIP_META[key] || {
            calculation: _t("Calculado a partir de métricas del período seleccionado."),
            meaning: this.shortDesc,
            recommendation: _t("Monitorear la evolución del indicador periódicamente."),
        };
    }

    onEnter() {
        this.state.showTip = true;
    }

    onLeave() {
        this.state.showTip = false;
    }

    async renderChart() {
        if (!this.chartRef.el) return;
        const echarts = await loadEcharts();
        if (!this._chart) {
            this._chart = echarts.init(this.chartRef.el);
        }
        this._chart.setOption(
            buildMaturityGaugeOption(this.displayValue, this.props.darkMode),
            { notMerge: true },
        );
        this._chart.resize();
    }
}

export class PurchaseMaturityGauges extends Component {
    static template = "gn_purchase_dashboard.MaturityGauges";
    static components = { MaturityGaugeCard };
    static props = {
        indexes: { type: Array, optional: true },
        loading: Boolean,
        darkMode: Boolean,
    };

    get items() {
        return this.props.indexes || [];
    }

    get average() {
        const items = this.items;
        if (!items.length) return 0;
        const sum = items.reduce((acc, i) => acc + (Number(i.value) || 0), 0);
        return Math.round((sum / items.length) * 10) / 10;
    }

    get generalStatus() {
        return maturityStatus(this.average);
    }

    get generalColor() {
        return maturityColor(this.average);
    }
}
