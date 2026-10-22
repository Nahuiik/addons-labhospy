/** @odoo-module **/

/** Gauge semicircular para Inventory Health Score. */

export function drawSemicircleGauge(canvas, score, options = {}) {
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;
    const cx = w / 2;
    const cy = h * 0.92;
    const radius = Math.min(w, h * 2) * 0.38;
    const val = Math.max(0, Math.min(100, Number(score) || 0));

    ctx.clearRect(0, 0, w, h);

    const color = val >= 90 ? "#059669" : val >= 75 ? "#10b981" : val >= 50 ? "#d97706" : "#dc2626";

    ctx.lineWidth = 14;
    ctx.lineCap = "round";
    ctx.strokeStyle = options.trackColor || "rgba(148,163,184,0.25)";
    ctx.beginPath();
    ctx.arc(cx, cy, radius, Math.PI, 2 * Math.PI);
    ctx.stroke();

    ctx.strokeStyle = color;
    ctx.beginPath();
    ctx.arc(cx, cy, radius, Math.PI, Math.PI + (Math.PI * val) / 100);
    ctx.stroke();

    ctx.fillStyle = options.textColor || "#0f172a";
    ctx.font = `700 ${Math.round(radius * 0.55)}px system-ui, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(`${Math.round(val)}%`, cx, cy - radius * 0.35);

    if (options.label) {
        ctx.font = `500 ${Math.round(radius * 0.22)}px system-ui, sans-serif`;
        ctx.fillStyle = options.subtextColor || "#64748b";
        ctx.fillText(options.label, cx, cy - radius * 0.05);
    }
}

export function animateCounter(from, to, duration, onUpdate) {
    const start = performance.now();
    const delta = to - from;
    const step = (now) => {
        const t = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - t, 3);
        onUpdate(from + delta * eased);
        if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
}
