/** @odoo-module **/

import { Component } from "@odoo/owl";

const COL_WIDTH = 220;
const ROW_HEIGHT = 88;
const NODE_W = 180;
const NODE_H = 52;
const PAD_X = 40;
const PAD_Y = 30;

/**
 * Compute layered positions: source locations | events | destinations.
 */
function layoutGraph(graph) {
    if (!graph?.nodes?.length) {
        return { nodes: [], edges: [], width: 0, height: 0 };
    }
    const nodeMap = Object.fromEntries(graph.nodes.map((n) => [n.id, { ...n }]));
    const events = graph.nodes
        .filter((n) => n.kind === "event")
        .sort((a, b) => (a.event_index || 0) - (b.event_index || 0));

    const positioned = {};
    events.forEach((ev, row) => {
        const y = PAD_Y + row * ROW_HEIGHT;
        positioned[ev.id] = {
            ...ev,
            x: PAD_X + COL_WIDTH,
            y,
            w: NODE_W,
            h: NODE_H,
        };
    });

    for (const edge of graph.edges || []) {
        const from = nodeMap[edge.from];
        const to = nodeMap[edge.to];
        if (!from || !to) {
            continue;
        }
        const targetEv = to.kind === "event" ? to : from.kind === "event" ? from : null;
        if (!targetEv) {
            continue;
        }
        const row = targetEv.event_index ?? 0;
        const y = PAD_Y + row * ROW_HEIGHT + NODE_H / 2;
        if (from.kind === "location" && !positioned[from.id]) {
            positioned[from.id] = {
                ...from,
                x: PAD_X,
                y: y - NODE_H / 2,
                w: NODE_W,
                h: NODE_H,
            };
        }
        if (to.kind === "location" && !positioned[to.id]) {
            positioned[to.id] = {
                ...to,
                x: PAD_X + COL_WIDTH * 2,
                y: y - NODE_H / 2,
                w: NODE_W,
                h: NODE_H,
            };
        }
    }

    // Place any orphan location nodes
    for (const node of graph.nodes) {
        if (!positioned[node.id]) {
            positioned[node.id] = {
                ...node,
                x: PAD_X,
                y: PAD_Y,
                w: NODE_W,
                h: NODE_H,
            };
        }
    }

    const nodes = Object.values(positioned);
    const maxRow = Math.max(0, events.length - 1);
    const height = PAD_Y * 2 + maxRow * ROW_HEIGHT + NODE_H;
    const width = PAD_X * 2 + COL_WIDTH * 2 + NODE_W;

    const edges = (graph.edges || []).map((edge) => {
        const from = positioned[edge.from];
        const to = positioned[edge.to];
        if (!from || !to) {
            return null;
        }
        const x1 = from.x + from.w;
        const y1 = from.y + from.h / 2;
        const x2 = to.x;
        const y2 = to.y + to.h / 2;
        const mx = (x1 + x2) / 2;
        return {
            ...edge,
            path: `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`,
            labelX: mx,
            labelY: (y1 + y2) / 2 - 6,
        };
    }).filter(Boolean);

    return { nodes, edges, width, height };
}

export class TraceabilityFlowMap extends Component {
    static template = "gn_product_traceability_widget.TraceabilityFlowMap";
    static props = {
        graph: { type: Object, optional: true },
        onNodeClick: { type: Function, optional: true },
    };

    get flowLayout() {
        return layoutGraph(this.props.graph || { nodes: [], edges: [] });
    }

    nodeClass(node) {
        return `gn_traceability_flowmap__node gn_traceability_flowmap__node--${node.kind} gn_traceability_flowmap__node--${node.tone || node.usage || "neutral"}`;
    }

    onClick(node) {
        if (this.props.onNodeClick) {
            this.props.onNodeClick(node);
        }
    }
}
