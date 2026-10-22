/** @odoo-module **/

export const DEFAULT_CONFIG = {
    spotRadius: 150,
    overlayOpacity: 0.15,
    lineMaxDist: 150,
    particleDensity: 8,
    theme: "dark",
    lightNodeColor: "#1F4AA8",
    darkNodeColor: "#59D8FF",
};

const MAX_PARTICLES = 400;
const ATTRIBUTE_LIST = [
    "data-spot-radius",
    "data-overlay-opacity",
    "data-line-max-dist",
    "data-particle-density",
    "data-theme",
    "data-light-color",
    "data-dark-color",
];

const ATTRACTION_INTENSITY = 0.07;
const MAX_SPEED = 1.8;

class JSAnimation {
    constructor(root) {
        this.root = root;
        this.container = root.querySelector(".js-animation-container") || root;
        this.fallback = this.container.querySelector(".js-animation-fallback") || null;
        this.eventTarget = root;
        this.canvas = document.createElement("canvas");
        this.canvas.setAttribute("role", "presentation");
        this.canvas.setAttribute("aria-hidden", "true");
        this.ctx = this.canvas.getContext("2d", { alpha: true });
        this.pointer = { x: 0, y: 0, active: false };
        this.particles = [];
        this.lastTs = null;
        this.rafId = null;
        this.resizeObserver = null;
        this.boundTick = (ts) => this._tick(ts);
        this.onMouseMove = (ev) => this._handleMouseMove(ev);
        this.onMouseLeave = () => this._deactivatePointer();
        this.onTouchMove = (ev) => this._handleTouchMove(ev);
        this.onTouchEnd = () => this._deactivatePointer();
        this.config = this._readConfig();
    }

    mount() {
        if (this.isMounted) {
            this.refreshConfig();
            return;
        }
        this.isMounted = true;
        this._purgeLegacyCanvases();
        this.container.appendChild(this.canvas);
        this._activatePointerDefault();
        this._bindEvents();
        this._resize();
        this._start();
    }

    unmount() {
        if (!this.isMounted) {
            return;
        }
        this.isMounted = false;
        this._stop();
        this._unbindEvents();
        if (this.canvas.parentElement) {
            this.canvas.parentElement.removeChild(this.canvas);
        }
        this.particles = [];
        this._showFallback();
    }

    refreshConfig() {
        const newConfig = this._readConfig();
        const hasChanged = Object.keys(newConfig).some((key) => newConfig[key] !== this.config[key]);
        if (hasChanged) {
            this.config = newConfig;
            this._resize(true);
        }
    }

    _bindEvents() {
        this.eventTarget.addEventListener("mousemove", this.onMouseMove, { passive: true });
        this.eventTarget.addEventListener("mouseleave", this.onMouseLeave, { passive: true });
        this.eventTarget.addEventListener("touchmove", this.onTouchMove, { passive: true });
        this.eventTarget.addEventListener("touchend", this.onTouchEnd, { passive: true });
        this.eventTarget.addEventListener("touchcancel", this.onTouchEnd, { passive: true });
        if (window.ResizeObserver) {
            this.resizeObserver = new ResizeObserver(() => this._resize());
            this.resizeObserver.observe(this.container);
        } else {
            this._fallbackResizeHandler = () => this._resize();
            window.addEventListener("resize", this._fallbackResizeHandler, { passive: true });
        }
    }

    _unbindEvents() {
        this.eventTarget.removeEventListener("mousemove", this.onMouseMove);
        this.eventTarget.removeEventListener("mouseleave", this.onMouseLeave);
        this.eventTarget.removeEventListener("touchmove", this.onTouchMove);
        this.eventTarget.removeEventListener("touchend", this.onTouchEnd);
        this.eventTarget.removeEventListener("touchcancel", this.onTouchEnd);
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
            this.resizeObserver = null;
        }
        if (this._fallbackResizeHandler) {
            window.removeEventListener("resize", this._fallbackResizeHandler);
            this._fallbackResizeHandler = null;
        }
    }

    _start() {
        if (this.rafId !== null) {
            cancelAnimationFrame(this.rafId);
        }
        this.lastTs = performance.now();
        this.rafId = requestAnimationFrame(this.boundTick);
    }

    _stop() {
        if (this.rafId !== null) {
            cancelAnimationFrame(this.rafId);
            this.rafId = null;
        }
    }

    _readConfig() {
        const dataset = this.root.dataset || {};
        const cfg = { ...DEFAULT_CONFIG };

        const toNumber = (value, fallback) => {
            const num = Number(value);
            return Number.isFinite(num) ? num : fallback;
        };

        if (dataset.spotRadius !== undefined) {
            cfg.spotRadius = Math.max(20, toNumber(dataset.spotRadius, DEFAULT_CONFIG.spotRadius));
        }
        if (dataset.overlayOpacity !== undefined) {
            const opacity = toNumber(dataset.overlayOpacity, DEFAULT_CONFIG.overlayOpacity);
            cfg.overlayOpacity = Math.min(Math.max(opacity, 0), 1);
        }
        if (dataset.lineMaxDist !== undefined) {
            cfg.lineMaxDist = Math.max(30, toNumber(dataset.lineMaxDist, DEFAULT_CONFIG.lineMaxDist));
        }
        if (dataset.particleDensity !== undefined) {
            const density = toNumber(dataset.particleDensity, DEFAULT_CONFIG.particleDensity);
            cfg.particleDensity = Math.max(0.01, density);
        }
        if (dataset.theme !== undefined) {
            const theme = String(dataset.theme).toLowerCase();
            cfg.theme = theme === "dark" || theme === "light" ? theme : DEFAULT_CONFIG.theme;
        }
        cfg.lightNodeColor = dataset.lightColor || DEFAULT_CONFIG.lightNodeColor;
        cfg.darkNodeColor = dataset.darkColor || DEFAULT_CONFIG.darkNodeColor;
        return cfg;
    }

    _activatePointerDefault() {
        const bounds = this.container.getBoundingClientRect();
        this.pointer.x = bounds.width / 2;
        this.pointer.y = bounds.height / 2;
        this.pointer.active = false;
    }

    _setPointer(x, y) {
        this.pointer.x = x;
        this.pointer.y = y;
        this.pointer.active = true;
    }

    _handleTouchMove(event) {
        if (!event.touches || !event.touches.length) {
            return;
        }
        const rect = this.container.getBoundingClientRect();
        const touch = event.touches[0];
        this._setPointer(touch.clientX - rect.left, touch.clientY - rect.top);
    }

    _handleMouseMove(event) {
        const rect = this.container.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        this._setPointer(x, y);
    }

    _deactivatePointer() {
        this.pointer.active = false;
    }

    _resize(forceRebuild = false) {
        const { width, height } = this._getContainerSize();
        if (width === 0 || height === 0) {
            return;
        }
        const needResize = this.canvas.width !== width || this.canvas.height !== height;
        if (needResize) {
            this.canvas.width = width;
            this.canvas.height = height;
            forceRebuild = true;
        }
        if (forceRebuild || !this.particles.length) {
            this._buildParticles(width, height);
        }
    }

    _getContainerSize() {
        const rect = this.container.getBoundingClientRect();
        const width = Math.max(Math.floor(rect.width), 1);
        const height = Math.max(Math.floor(rect.height), 1);
        return { width, height };
    }

    _buildParticles(width, height) {
        const target = Math.min(
            MAX_PARTICLES,
            Math.max(8, Math.round((width * height * this.config.particleDensity) / 100000))
        );
        const speedFactor = 0.35;
        this.particles = new Array(target).fill(null).map(() => ({
            x: Math.random() * width,
            y: Math.random() * height,
            vx: (Math.random() - 0.5) * speedFactor,
            vy: (Math.random() - 0.5) * speedFactor,
        }));
    }

    _tick(timestamp) {
        if (!this.isMounted) {
            return;
        }
        const deltaMs = this.lastTs ? timestamp - this.lastTs : 16;
        this.lastTs = timestamp;
        const delta = Math.min(deltaMs / 16.6667, 2);
        this._updateParticles(delta);
        this._render();
        this.rafId = requestAnimationFrame(this.boundTick);
    }

    _updateParticles(delta) {
        const { width, height } = this.canvas;
        const drift = 0.0025 * delta;
        const pointer = this.pointer.active
            ? {
                  x: this.pointer.x,
                  y: this.pointer.y,
                  radius: Math.max(this.config.spotRadius, 40),
              }
            : null;
        for (const particle of this.particles) {
            particle.vx += (Math.random() - 0.5) * drift;
            particle.vy += (Math.random() - 0.5) * drift;
            if (pointer) {
                const dx = pointer.x - particle.x;
                const dy = pointer.y - particle.y;
                const distSq = dx * dx + dy * dy;
                const radiusSq = pointer.radius * pointer.radius;
                if (distSq < radiusSq && distSq > 0.0001) {
                    const dist = Math.sqrt(distSq);
                    const strength = (1 - dist / pointer.radius) * ATTRACTION_INTENSITY * delta;
                    const ux = dx / dist;
                    const uy = dy / dist;
                    particle.vx += ux * strength;
                    particle.vy += uy * strength;
                }
            }

            const speed = Math.hypot(particle.vx, particle.vy);
            if (speed > MAX_SPEED) {
                const scale = MAX_SPEED / speed;
                particle.vx *= scale;
                particle.vy *= scale;
            }

            particle.x += particle.vx * delta * 3;
            particle.y += particle.vy * delta * 3;

            if (particle.x < 0 || particle.x > width) {
                particle.vx *= -1;
                particle.x = Math.min(Math.max(particle.x, 0), width);
            }
            if (particle.y < 0 || particle.y > height) {
                particle.vy *= -1;
                particle.y = Math.min(Math.max(particle.y, 0), height);
            }
        }
    }

    _render() {
        const ctx = this.ctx;
        if (!ctx) {
            return;
        }
        this._hideFallback();
        const { width, height } = this.canvas;
        const { theme, overlayOpacity, spotRadius } = this.config;

        const themeColors = theme === "dark"
            ? { background: "#05070f", overlay: `rgba(0, 8, 20, ${overlayOpacity})`, node: this.config.darkNodeColor }
            : { background: "#f5f8ff", overlay: `rgba(255, 255, 255, ${overlayOpacity})`, node: this.config.lightNodeColor };

        ctx.clearRect(0, 0, width, height);
        ctx.fillStyle = themeColors.background;
        ctx.fillRect(0, 0, width, height);

        if (overlayOpacity > 0) {
            ctx.save();
            ctx.fillStyle = themeColors.overlay;
            ctx.fillRect(0, 0, width, height);

            const pointer = this.pointer.active
                ? { x: this.pointer.x, y: this.pointer.y }
                : { x: width / 2, y: height / 2 };
            const gradient = ctx.createRadialGradient(pointer.x, pointer.y, 0, pointer.x, pointer.y, spotRadius);
            const coneIntensity = Math.min(Math.max(overlayOpacity, 0), 1);
            gradient.addColorStop(0, `rgba(0, 0, 0, ${coneIntensity})`);
            gradient.addColorStop(1, "rgba(0, 0, 0, 0)");

            ctx.globalCompositeOperation = "destination-out";
            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.arc(pointer.x, pointer.y, spotRadius, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();
        }

        this._drawConnections(ctx, themeColors.node);
        this._drawParticles(ctx, themeColors.node);
    }

    _drawParticles(ctx, color) {
        ctx.fillStyle = color;
        for (const particle of this.particles) {
            ctx.beginPath();
            ctx.arc(particle.x, particle.y, 2, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    _drawConnections(ctx, color) {
        const maxDist = this.config.lineMaxDist;
        if (this.particles.length < 2) {
            return;
        }
        const grid = new Map();
        const cellSize = maxDist;
        const cellKey = (x, y) => `${x}:${y}`;

        for (let index = 0; index < this.particles.length; index++) {
            const particle = this.particles[index];
            const col = Math.floor(particle.x / cellSize);
            const row = Math.floor(particle.y / cellSize);
            const key = cellKey(col, row);
            if (!grid.has(key)) {
                grid.set(key, []);
            }
            grid.get(key).push(index);
        }

        ctx.strokeStyle = color;
        ctx.lineWidth = 1;

        for (let index = 0; index < this.particles.length; index++) {
            const particle = this.particles[index];
            const col = Math.floor(particle.x / cellSize);
            const row = Math.floor(particle.y / cellSize);
            for (let i = col - 1; i <= col + 1; i++) {
                for (let j = row - 1; j <= row + 1; j++) {
                    const key = cellKey(i, j);
                    const neighbors = grid.get(key);
                    if (!neighbors) {
                        continue;
                    }
                    for (const neighborIndex of neighbors) {
                        if (neighborIndex <= index) {
                            continue;
                        }
                        const neighbor = this.particles[neighborIndex];
                        const dx = neighbor.x - particle.x;
                        const dy = neighbor.y - particle.y;
                        const dist = Math.sqrt(dx * dx + dy * dy);
                        if (dist > maxDist) {
                            continue;
                        }
                        const alpha = 1 - dist / maxDist;
                        ctx.globalAlpha = Math.max(0.05, Math.min(alpha, 1));
                        ctx.beginPath();
                        ctx.moveTo(particle.x, particle.y);
                        ctx.lineTo(neighbor.x, neighbor.y);
                        ctx.stroke();
                    }
                }
            }
        }
        ctx.globalAlpha = 1;
    }

    _purgeLegacyCanvases() {
        const nodes = Array.from(this.container.childNodes);
        for (const node of nodes) {
            if (node === this.canvas) {
                continue;
            }
            if (node instanceof Element && node.classList.contains("js-animation-fallback")) {
                continue;
            }
            if (node instanceof HTMLCanvasElement) {
                node.remove();
                continue;
            }
            if (node instanceof HTMLBRElement) {
                node.remove();
                continue;
            }
            if (node.nodeType === Node.TEXT_NODE && !node.textContent.trim()) {
                node.remove();
            }
        }
    }

    _hideFallback() {
        if (this.fallback) {
            this.fallback.classList.add("is-hidden");
        }
    }

    _showFallback() {
        if (this.fallback) {
            this.fallback.classList.remove("is-hidden");
        }
    }
}

const instances = new Map();
let observer = null;
let initialized = false;

export function mountElement(element) {
    if (instances.has(element)) {
        instances.get(element).refreshConfig();
        return;
    }
    const instance = new JSAnimation(element);
    instance.mount();
    instances.set(element, instance);
}

export function unmountElement(element) {
    const instance = instances.get(element);
    if (!instance) {
        return;
    }
    instance.unmount();
    instances.delete(element);
}

export function refreshElement(element) {
    const instance = instances.get(element);
    if (instance) {
        instance.refreshConfig();
    } else if (element instanceof Element && element.classList.contains("s-js-animation")) {
        mountElement(element);
    }
}

function scanAndMount(root = document) {
    const elements = root.querySelectorAll ? root.querySelectorAll(".s-js-animation") : [];
    elements.forEach((element) => mountElement(element));
    if (root instanceof Element && root.classList && root.classList.contains("s-js-animation")) {
        mountElement(root);
    }
}

function scanAndUnmount(nodes) {
    nodes.forEach((node) => {
        if (!(node instanceof Element)) {
            return;
        }
        if (instances.has(node)) {
            unmountElement(node);
        }
        const descendants = node.querySelectorAll ? node.querySelectorAll(".s-js-animation") : [];
        descendants.forEach((child) => unmountElement(child));
    });
}

function handleAttributeMutation(mutation) {
    const target = mutation.target;
    if (!(target instanceof Element)) {
        return;
    }
    if (!target.classList.contains("s-js-animation")) {
        return;
    }
    const attrName = mutation.attributeName;
    if (attrName && ATTRIBUTE_LIST.includes(attrName)) {
        const instance = instances.get(target);
        if (instance) {
            instance.refreshConfig();
        }
    }
}

function init() {
    if (initialized || !document.body) {
        return;
    }
    initialized = true;
    scanAndMount(document);

    observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            if (mutation.type === "childList") {
                if (mutation.addedNodes.length) {
                    mutation.addedNodes.forEach((node) => scanAndMount(node));
                }
                if (mutation.removedNodes.length) {
                    scanAndUnmount([...mutation.removedNodes]);
                }
            } else if (mutation.type === "attributes") {
                handleAttributeMutation(mutation);
            }
        }
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ATTRIBUTE_LIST,
    });

    document.addEventListener("visibilitychange", () => {
        instances.forEach((instance) => {
            if (document.hidden) {
                instance._stop();
            } else {
                instance._start();
            }
        });
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}

export default JSAnimation;

if (typeof window !== "undefined") {
    window.__gnWebsitePlexus = window.__gnWebsitePlexus || {};
    window.__gnWebsitePlexus.animation = {
        DEFAULT_CONFIG,
        mountElement,
        refreshElement,
        unmountElement,
    };
}
