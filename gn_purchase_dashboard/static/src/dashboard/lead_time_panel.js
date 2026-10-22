/** @odoo-module **/

import { Component, onPatched, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

const TARGET_DAYS = 3.0;

function round1(n) {
    return Math.round((Number(n) || 0) * 10) / 10;
}

function distributionStats(values) {
    const dist = (values || []).map(Number).filter((v) => !Number.isNaN(v));
    if (!dist.length) {
        return { min: 0, max: 0, median: 0, std: 0, avg: 0, count: 0 };
    }
    const sorted = [...dist].sort((a, b) => a - b);
    const avg = sorted.reduce((a, b) => a + b, 0) / sorted.length;
    const mid = Math.floor(sorted.length / 2);
    const median = sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
    const variance = sorted.reduce((acc, v) => acc + (v - avg) ** 2, 0) / sorted.length;
    return {
        min: sorted[0],
        max: sorted[sorted.length - 1],
        median: round1(median),
        std: round1(Math.sqrt(variance)),
        avg: round1(avg),
        count: sorted.length,
    };
}

function chunkSparkline(values, buckets = 12) {
    const dist = values || [];
    if (!dist.length) return [];
    const size = Math.max(1, Math.ceil(dist.length / buckets));
    const points = [];
    for (let i = 0; i < buckets; i += 1) {
        const chunk = dist.slice(i * size, (i + 1) * size);
        if (!chunk.length) break;
        points.push(round1(chunk.reduce((a, b) => a + b, 0) / chunk.length));
    }
    return points;
}

export class PurchaseLeadTimePanel extends Component {
    static template = "gn_purchase_dashboard.LeadTimePanel";
    static props = {
        config: { type: Object, optional: true },
        kpi: { type: Object, optional: true },
        receipts: { type: Object, optional: true },
        urgentCount: { type: Number, optional: true },
        loading: { type: Boolean, optional: true },
        darkMode: { type: Boolean, optional: true },
    };

    setup() {
        this.state = useState({ pulse: false, hoverSpark: null });
        this._prevAvg = this.avgDays;
        onPatched(() => {
            const next = this.avgDays;
            if (next !== this._prevAvg) {
                this._prevAvg = next;
                this.state.pulse = true;
                setTimeout(() => { this.state.pulse = false; }, 550);
            }
        });
    }

    get avgDays() {
        return round1(this.props.config?.avg_days ?? this.props.kpi?.value ?? 0);
    }

    get targetDays() {
        return TARGET_DAYS;
    }

    get stats() {
        return distributionStats(this.props.config?.distribution);
    }

    get sparkPoints() {
        return chunkSparkline(this.props.config?.distribution, 12);
    }

    get sparkStats() {
        const pts = this.sparkPoints;
        if (!pts.length) return { trend: "—", avg: "—", min: "—", max: "—" };
        return {
            trend: pts[pts.length - 1] < pts[0] ? _t("Mejora") : pts[pts.length - 1] > pts[0] ? _t("Alza") : _t("Estable"),
            avg: round1(pts.reduce((a, b) => a + b, 0) / pts.length),
            min: Math.min(...pts),
            max: Math.max(...pts),
        };
    }

    get sparkPath() {
        const pts = this.sparkPoints;
        if (pts.length < 2) return "";
        const w = 120;
        const h = 36;
        const max = Math.max(...pts, 1);
        const min = Math.min(...pts, 0);
        const range = max - min || 1;
        return pts.map((v, i) => {
            const x = (i / (pts.length - 1)) * w;
            const y = h - ((v - min) / range) * h;
            return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
        }).join(" ");
    }

    get previousAvg() {
        const kpi = this.props.kpi;
        if (!kpi?.value) return null;
        const pct = kpi.variation_pct || 0;
        if (!pct) return round1(kpi.value);
        return round1(kpi.value / (1 + pct / 100));
    }

    get deltaDays() {
        const prev = this.previousAvg;
        if (prev === null) return 0;
        return round1(prev - this.avgDays);
    }

    get deltaLabel() {
        const d = this.deltaDays;
        if (!d) return _t("Sin cambio vs período anterior");
        const abs = Math.abs(d).toFixed(1);
        return d > 0
            ? _t("Mejoró %s d vs período anterior", abs)
            : _t("Empeoró %s d vs período anterior", abs);
    }

    get statusClass() {
        if (this.avgDays <= this.targetDays) return "success";
        if (this.avgDays <= this.targetDays * 1.25) return "warn";
        return "danger";
    }

    get deltaIcon() {
        if (this.deltaDays > 0) return "fa-arrow-down";
        if (this.deltaDays < 0) return "fa-arrow-up";
        return "fa-minus";
    }

    get goalPct() {
        if (!this.targetDays) return 0;
        const pct = 100 - ((this.avgDays - this.targetDays) / this.targetDays) * 100;
        return Math.max(0, Math.min(100, Math.round(pct)));
    }

    get breakdownRows() {
        const r = this.props.receipts || {};
        const urgent = this.props.urgentCount || 0;
        const rows = [
            { key: "on_time", label: _t("Recepciones a tiempo"), value: r.on_time || 0, color: "success" },
            { key: "late", label: _t("Recepciones tardías"), value: r.late || 0, color: "danger" },
            { key: "partial", label: _t("Recepciones parciales"), value: r.partial || 0, color: "warn" },
            { key: "urgent", label: _t("Órdenes urgentes"), value: urgent, color: "info" },
        ];
        const total = rows.reduce((a, b) => a + b.value, 0) || 1;
        return rows.filter((row) => row.value > 0).map((row) => ({
            ...row,
            pct: Math.round((row.value / total) * 100),
        }));
    }

    get miniKpis() {
        const s = this.stats;
        return [
            { label: _t("Mínimo"), value: `${round1(s.min)} d` },
            { label: _t("Máximo"), value: `${round1(s.max)} d` },
            { label: _t("Mediana"), value: `${s.median} d` },
            { label: _t("Desv. std."), value: `${s.std} d` },
        ];
    }

    get fastestVendors() {
        return (this.props.config?.fastest || []).slice(0, 2);
    }

    get slowestVendors() {
        return (this.props.config?.slowest || []).slice(0, 2);
    }

    get aiInsight() {
        const parts = [];
        const d = this.deltaDays;
        if (d > 0) {
            parts.push(_t("El Lead Time mejoró %s días respecto al período anterior.", Math.abs(d).toFixed(1)));
        } else if (d < 0) {
            parts.push(_t("El Lead Time aumentó %s días respecto al período anterior.", Math.abs(d).toFixed(1)));
        }
        const fastest = this.fastestVendors[0];
        const slowest = this.slowestVendors[0];
        if (fastest?.name) {
            parts.push(_t("La mejora se concentra en proveedores como %s (%s d).", fastest.name, round1(fastest.days)));
        }
        if ((this.props.urgentCount || 0) > 0) {
            parts.push(_t("Hay %s órdenes urgentes que pueden elevar el promedio.", this.props.urgentCount));
        }
        if (slowest?.name && slowest.days > this.avgDays * 1.5) {
            parts.push(_t("%s concentra los mayores retrasos (%s d).", slowest.name, round1(slowest.days)));
        }
        const late = this.props.receipts?.late || 0;
        if (late > 0) {
            parts.push(_t("Se detectan %s recepciones tardías en el período.", late));
        }
        return parts[0] || _t("El Lead Time promedio es de %s días frente a una meta de %s.", this.avgDays, this.targetDays);
    }

    onSparkMove(ev) {
        const pts = this.sparkPoints;
        if (!pts.length) return;
        const rect = ev.currentTarget.getBoundingClientRect();
        const ratio = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width));
        const idx = Math.min(pts.length - 1, Math.round(ratio * (pts.length - 1)));
        this.state.hoverSpark = { idx, value: pts[idx] };
    }

    onSparkLeave() {
        this.state.hoverSpark = null;
    }
}
