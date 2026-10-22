/** @odoo-module **/

import { Component } from "@odoo/owl";

export class WbEmptyState extends Component {
    static template = "gn_banks_balance.WbEmptyState";
    static props = {
        icon: { type: String, optional: true },
        tone: { type: String, optional: true },
        title: { type: String, optional: true },
        description: { type: String, optional: true },
        hint: { type: String, optional: true },
        actionLabel: { type: String, optional: true },
        onAction: { type: Function, optional: true },
        compact: { type: Boolean, optional: true },
    };
    static defaultProps = {
        icon: "fa-inbox",
        tone: "neutral",
        compact: false,
    };

    get toneClass() {
        return `gn-empty--${this.props.tone}`;
    }
}

export class WbLoadingSkeleton extends Component {
    static template = "gn_banks_balance.WbLoadingSkeleton";
    static props = {
        variant: { type: String, optional: true },
        rows: { type: Number, optional: true },
    };
    static defaultProps = {
        variant: "card",
        rows: 3,
    };

    get rowsArray() {
        return Array.from({ length: this.props.rows || 1 });
    }
}
