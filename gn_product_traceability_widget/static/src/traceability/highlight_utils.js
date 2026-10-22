/** @odoo-module **/

/**
 * Split text into match/non-match segments for safe OWL rendering.
 * @returns {Array<{text: string, match: boolean}>}
 */
export function highlightParts(text, search) {
    const raw = text || "";
    if (!search || !raw) {
        return [{ text: raw, match: false }];
    }
    const term = search.toLowerCase();
    const lower = raw.toLowerCase();
    const parts = [];
    let cursor = 0;
    let idx = lower.indexOf(term, cursor);
    while (idx !== -1) {
        if (idx > cursor) {
            parts.push({ text: raw.slice(cursor, idx), match: false });
        }
        parts.push({ text: raw.slice(idx, idx + term.length), match: true });
        cursor = idx + term.length;
        idx = lower.indexOf(term, cursor);
    }
    if (cursor < raw.length) {
        parts.push({ text: raw.slice(cursor), match: false });
    }
    return parts.length ? parts : [{ text: raw, match: false }];
}

export function fieldIsHighlighted(event, fieldName) {
    return (event.highlight_fields || []).includes(fieldName);
}
