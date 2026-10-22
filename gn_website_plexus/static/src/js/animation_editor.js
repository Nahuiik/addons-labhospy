/** @odoo-module **/

import {
    DEFAULT_CONFIG,
    mountElement,
    refreshElement,
    unmountElement,
} from "@gn_website_plexus/js/animation";

const PANEL_CLASS = "o_gn_plexus_panel";
const PANEL_TOGGLE_CLASS = "o_gn_plexus_panel_toggle";
const PANEL_DATA_FLAG = "gnPlexusPanel";

const ATTRIBUTE_DEFINITIONS = [
    {
        key: "spotRadius",
        attr: "data-spot-radius",
        label: "Radio del foco",
        type: "range",
        min: 40,
        max: 480,
        step: 10,
        format(value) {
            return `${Math.round(value)} px`;
        },
    },
    {
        key: "overlayOpacity",
        attr: "data-overlay-opacity",
        label: "Opacidad",
        type: "range",
        min: 0,
        max: 1,
        step: 0.01,
        format(value) {
            return value.toFixed(2);
        },
    },
    {
        key: "lineMaxDist",
        attr: "data-line-max-dist",
        label: "Distancia de líneas",
        type: "range",
        min: 60,
        max: 500,
        step: 5,
        format(value) {
            return `${Math.round(value)} px`;
        },
    },
    {
        key: "particleDensity",
        attr: "data-particle-density",
        label: "Densidad",
        type: "range",
        min: 1,
        max: 8,
        step: 0.1,
        format(value) {
            return value.toFixed(2);
        },
    },
    {
        key: "lightNodeColor",
        attr: "data-light-color",
        label: "Color líneas (claro)",
        type: "color",
        format(value) {
            return value.toUpperCase();
        },
    },
    {
        key: "darkNodeColor",
        attr: "data-dark-color",
        label: "Color líneas (oscuro)",
        type: "color",
        format(value) {
            return value.toUpperCase();
        },
    },
];

const THEME_OPTIONS = [
    { value: "light", label: "Tema claro" },
    { value: "dark", label: "Tema oscuro" },
];

const OBSERVED_ATTRIBUTES = ATTRIBUTE_DEFINITIONS.map(({ attr }) => attr).concat([
    "data-theme",
    "data-panel-hidden",
]);

function init() {
    setupDocument(document);
    watchIframes(document);
}

function setupDocument(doc) {
    if (!doc || doc.__gnPlexusInitialized || !isEditableDocument(doc)) {
        return;
    }
    doc.__gnPlexusInitialized = true;
    doc.querySelectorAll(".s-js-animation").forEach((section) => enhanceSection(section));
    const observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            mutation.addedNodes.forEach((node) => {
                if (!(node instanceof doc.defaultView.Element)) {
                    return;
                }
                if (node.classList.contains("s-js-animation")) {
                    enhanceSection(node);
                }
                node.querySelectorAll?.(".s-js-animation").forEach((child) => enhanceSection(child));
            });
            mutation.removedNodes.forEach((node) => {
                if (!(node instanceof doc.defaultView.Element)) {
                    return;
                }
                if (node.classList.contains("s-js-animation")) {
                    teardownSection(node);
                }
                node.querySelectorAll?.(".s-js-animation").forEach((child) => teardownSection(child));
            });
        }
    });
    observer.observe(doc.body || doc.documentElement, { childList: true, subtree: true });
    doc.__gnPlexusObserver = observer;
}

function watchIframes(rootDoc) {
    const handled = new WeakSet();
    const scan = () => {
        rootDoc.querySelectorAll("iframe").forEach((iframe) => {
            if (!(iframe instanceof HTMLIFrameElement) || handled.has(iframe)) {
                return;
            }
            handled.add(iframe);
            const setup = () => {
                try {
                    setupDocument(iframe.contentDocument);
                } catch (error) {
                    // ignore cross-origin frames
                }
            };
            iframe.addEventListener("load", setup);
            setup();
        });
    };
    scan();
    const observer = new MutationObserver(scan);
    observer.observe(rootDoc.body || rootDoc.documentElement, { childList: true, subtree: true });
}

function enhanceSection(section) {
    if (!isEditableDocument(section.ownerDocument)) {
        return;
    }
    if (!(section instanceof section.ownerDocument.defaultView.Element)) {
        return;
    }
    ensureContentSlot(section);
    let panel = section.querySelector(`.${PANEL_CLASS}`);
    if (!panel) {
        panel = buildPanel(section);
        section.appendChild(panel);
        section.dataset[PANEL_DATA_FLAG] = "1";
        observeSectionAttributes(section);
        section.removeAttribute("data-panel-hidden");
    }
    ensureToggle(section);
    syncPanel(section);
    syncVisibility(section);
    mountElement(section);
    refreshElement(section);
}

function teardownSection(section) {
    section.__gnPlexusAttrObserver?.disconnect?.();
    delete section.__gnPlexusAttrObserver;
    delete section.dataset[PANEL_DATA_FLAG];
    section.querySelector(`.${PANEL_CLASS}`)?.remove();
    section.querySelector(`.${PANEL_TOGGLE_CLASS}`)?.remove();
    unmountElement(section);
}

function buildPanel(section) {
    const doc = section.ownerDocument;
    const panel = doc.createElement("div");
    panel.className = PANEL_CLASS;
    panel.dataset.role = "gn-plexus-panel";

    const header = doc.createElement("div");
    header.className = "o_gn_plexus_panel_header";
    const title = doc.createElement("span");
    title.className = "o_gn_plexus_panel_title";
    title.textContent = "Animación Plexus";
    header.appendChild(title);

    const hideButton = doc.createElement("button");
    hideButton.type = "button";
    hideButton.className = "o_gn_plexus_panel_close";
    hideButton.textContent = "Ocultar";
    hideButton.addEventListener("click", () => setPanelHidden(section, true));
    header.appendChild(hideButton);
    panel.appendChild(header);

    ATTRIBUTE_DEFINITIONS.forEach((definition) => {
        const row = doc.createElement("label");
        row.className = "o_gn_plexus_panel_row";
        row.textContent = definition.label;

        const badge = doc.createElement("span");
        badge.className = "o_gn_plexus_value";
        badge.dataset.field = definition.key;
        row.appendChild(badge);

        const input = doc.createElement("input");
        input.type = definition.type;
        if (definition.type === "range") {
            input.min = String(definition.min);
            input.max = String(definition.max);
            input.step = String(definition.step);
        }
        input.className = "o_gn_plexus_input";
        input.dataset.field = definition.key;
        input.addEventListener("input", () => handleInput(section, definition, input, badge));
        row.appendChild(input);

        panel.appendChild(row);
    });

    const themeRow = doc.createElement("div");
    themeRow.className = "o_gn_plexus_panel_row";
    const themeLabel = doc.createElement("span");
    themeLabel.textContent = "Tema";
    themeRow.appendChild(themeLabel);
    const themeSelect = doc.createElement("select");
    themeSelect.className = "o_gn_plexus_input";
    themeSelect.dataset.field = "theme";
    THEME_OPTIONS.forEach(({ value, label }) => {
        const option = doc.createElement("option");
        option.value = value;
        option.textContent = label;
        themeSelect.appendChild(option);
    });
    themeSelect.addEventListener("change", () => {
        section.setAttribute("data-theme", themeSelect.value === "dark" ? "dark" : "light");
        refreshElement(section);
        syncPanel(section);
    });
    themeRow.appendChild(themeSelect);
    panel.appendChild(themeRow);

    const resetButton = doc.createElement("button");
    resetButton.type = "button";
    resetButton.className = "o_gn_plexus_reset o_button o_button_secondary";
    resetButton.textContent = "Restablecer valores";
    resetButton.addEventListener("click", () => {
        applyDefaults(section);
        syncPanel(section);
        refreshElement(section);
    });
    panel.appendChild(resetButton);

    return panel;
}

function ensureToggle(section) {
    const doc = section.ownerDocument;
    let toggle = section.querySelector(`.${PANEL_TOGGLE_CLASS}`);
    if (!toggle) {
        toggle = doc.createElement("button");
        toggle.type = "button";
        toggle.className = PANEL_TOGGLE_CLASS;
        toggle.textContent = "Mostrar controles";
        toggle.setAttribute("aria-label", "Mostrar controles del snippet");
        toggle.tabIndex = -1;
        toggle.addEventListener("click", () => setPanelHidden(section, false));
        section.appendChild(toggle);
    }
    return toggle;
}

function ensureContentSlot(section) {
    const doc = section.ownerDocument;
    const canvas = section.querySelector(".js-animation-container");
    let slot = section.querySelector(".o_gn_plexus_content");
    if (!slot) {
        slot = doc.createElement("div");
        slot.className = "o_gn_plexus_content oe_structure";
        slot.dataset.gnPlexusSlot = "content";
        if (canvas && canvas.nextSibling) {
            section.insertBefore(slot, canvas.nextSibling);
        } else {
            section.appendChild(slot);
        }
    } else if (!slot.classList.contains("oe_structure")) {
        slot.classList.add("oe_structure");
    }
}

function handleInput(section, definition, input, badge) {
    let value;
    if (definition.type === "range") {
        const parsed = Number.parseFloat(input.value);
        const fallback = DEFAULT_CONFIG[definition.key];
        value = clamp(definition, Number.isFinite(parsed) ? parsed : fallback);
    } else if (definition.type === "color") {
        value = normalizeColor(input.value, DEFAULT_CONFIG[definition.key]);
    } else {
        value = input.value;
    }
    input.value = String(value);
    section.setAttribute(definition.attr, String(value));
    if (badge) {
        badge.textContent = definition.format(value);
    }
    refreshElement(section);
}

function applyDefaults(section) {
    ATTRIBUTE_DEFINITIONS.forEach((definition) => {
        let value = DEFAULT_CONFIG[definition.key];
        if (definition.type === "color") {
            value = normalizeColor(value, value);
        }
        section.setAttribute(definition.attr, String(value));
    });
    section.setAttribute("data-theme", DEFAULT_CONFIG.theme);
}

function observeSectionAttributes(section) {
    if (section.__gnPlexusAttrObserver) {
        return;
    }
    const observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            if (!mutation.attributeName) {
                continue;
            }
            if (OBSERVED_ATTRIBUTES.includes(mutation.attributeName)) {
                syncPanel(section);
                syncVisibility(section);
            }
        }
    });
    observer.observe(section, {
        attributes: true,
        attributeFilter: OBSERVED_ATTRIBUTES,
    });
    section.__gnPlexusAttrObserver = observer;
}

function syncPanel(section) {
    const panel = section.querySelector(`.${PANEL_CLASS}`);
    if (!panel) {
        return;
    }
    ATTRIBUTE_DEFINITIONS.forEach((definition) => {
        const input = panel.querySelector(`.o_gn_plexus_input[data-field="${definition.key}"]`);
        const badge = panel.querySelector(`.o_gn_plexus_value[data-field="${definition.key}"]`);
        const value = getCurrentValue(section, definition);
        if (section.getAttribute(definition.attr) === null) {
            section.setAttribute(definition.attr, String(value));
        }
        if (input) {
            input.value = String(value);
        }
        if (badge) {
            badge.textContent = definition.format(value);
        }
    });
    const themeSelect = panel.querySelector("select[data-field='theme']");
    if (themeSelect) {
        const theme = (section.dataset.theme || DEFAULT_CONFIG.theme || "dark").toLowerCase();
        themeSelect.value = theme === "dark" ? "dark" : "light";
    }
}

function syncVisibility(section) {
    const hidden = section.getAttribute("data-panel-hidden") === "1";
    const panel = section.querySelector(`.${PANEL_CLASS}`);
    if (panel) {
        panel.setAttribute("aria-hidden", hidden ? "true" : "false");
        panel.style.display = hidden ? "none" : "";
    }
    const toggle = section.querySelector(`.${PANEL_TOGGLE_CLASS}`);
    if (toggle) {
        toggle.setAttribute("aria-hidden", hidden ? "false" : "true");
        toggle.tabIndex = hidden ? 0 : -1;
        toggle.style.display = hidden ? "inline-flex" : "none";
    }
}

function setPanelHidden(section, hidden) {
    if (hidden) {
        section.setAttribute("data-panel-hidden", "1");
    } else {
        section.removeAttribute("data-panel-hidden");
    }
    syncVisibility(section);
    if (!hidden) {
        const firstControl = section.querySelector(`.${PANEL_CLASS} .o_gn_plexus_input`);
        firstControl?.focus({ preventScroll: true });
    }
}

function getCurrentValue(section, definition) {
    const raw = section.getAttribute(definition.attr);
    if (definition.type === "color") {
        return normalizeColor(raw, DEFAULT_CONFIG[definition.key]);
    }
    if (raw !== null) {
        const numeric = Number(raw);
        if (Number.isFinite(numeric)) {
            return clamp(definition, numeric);
        }
    }
    return DEFAULT_CONFIG[definition.key];
}

function clamp(definition, value) {
    if (typeof definition.min === "number") {
        value = Math.max(definition.min, value);
    }
    if (typeof definition.max === "number") {
        value = Math.min(definition.max, value);
    }
    return value;
}

function normalizeColor(value, fallback) {
    const base = typeof fallback === "string" ? fallback : "#000000";
    if (typeof value !== "string") {
        return base.toUpperCase();
    }
    const trimmed = value.trim();
    if (/^#[0-9a-fA-F]{6}$/.test(trimmed)) {
        return trimmed.toUpperCase();
    }
    if (/^#[0-9a-fA-F]{3}$/.test(trimmed)) {
        const r = trimmed[1];
        const g = trimmed[2];
        const b = trimmed[3];
        return `#${r}${r}${g}${g}${b}${b}`.toUpperCase();
    }
    return base.toUpperCase();
}

function isEditableDocument(doc) {
    const html = doc?.documentElement;
    if (html?.dataset?.editable === "1") {
        return true;
    }
    return doc?.body?.classList?.contains("o_edit_mode") || false;
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
} else {
    init();
}
