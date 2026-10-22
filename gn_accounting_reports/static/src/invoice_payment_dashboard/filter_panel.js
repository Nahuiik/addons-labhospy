/** @odoo-module **/

import { Component } from "@odoo/owl";
import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";
import { _t } from "@web/core/l10n/translation";

export class InvPayFilterPanel extends Component {
    static template = "gn_accounting_reports.InvPayFilterPanel";
    static components = { MultiRecordSelector };
    static props = {
        filters: Object,
        options: Object,
        expanded: Boolean,
        collapsed: Boolean,
        chips: { type: Array, optional: true },
        onFilterChange: Function,
        onPresetChange: Function,
        onToggleExpand: Function,
        onExpand: Function,
        onReset: Function,
        onApply: Function,
    };

    get hasNonDefaultFilters() {
        const f = this.props.filters;
        return (
            f.branch_ids?.length || f.user_ids?.length || f.partner_ids?.length
            || f.journal_ids?.length || f.categ_ids?.length
            || f.payment_state !== "all" || f.overdue_only
            || f.compare_mode !== "previous" || f.search
            || f.invoice_date_from || f.invoice_date_to
            || f.amount_min || f.amount_max
            || f.credit_term_filter !== "all"
        );
    }

    onField(ev, field) {
        this.props.onFilterChange({ [field]: ev.target.value });
    }

    onCheckbox(ev, field) {
        this.props.onFilterChange({ [field]: ev.target.checked });
    }

    get branchSelectorProps() {
        const cid = this.props.filters.company_id;
        return {
            resModel: "res.branch",
            resIds: this.props.filters.branch_ids || [],
            domain: cid ? [["company_id", "=", cid]] : [["id", "=", 0]],
            update: (ids) => this.props.onFilterChange({ branch_ids: ids }),
            placeholder: _t("Sucursales"),
        };
    }

    get userSelectorProps() {
        const cid = this.props.filters.company_id;
        return {
            resModel: "res.users",
            resIds: this.props.filters.user_ids || [],
            domain: cid
                ? [["company_ids", "in", cid], ["share", "=", false]]
                : [["share", "=", false]],
            update: (ids) => this.props.onFilterChange({ user_ids: ids }),
            placeholder: _t("Asesores"),
        };
    }

    get partnerSelectorProps() {
        return {
            resModel: "res.partner",
            resIds: this.props.filters.partner_ids || [],
            domain: [["customer_rank", ">", 0]],
            update: (ids) => this.props.onFilterChange({ partner_ids: ids }),
            placeholder: _t("Clientes"),
        };
    }

    get journalSelectorProps() {
        const cid = this.props.filters.company_id;
        return {
            resModel: "account.journal",
            resIds: this.props.filters.journal_ids || [],
            domain: cid
                ? [["type", "in", ["bank", "cash"]], ["company_id", "=", cid]]
                : [["type", "in", ["bank", "cash"]]],
            update: (ids) => this.props.onFilterChange({ journal_ids: ids }),
            placeholder: _t("Bancos / diarios"),
        };
    }

    get categSelectorProps() {
        return {
            resModel: "product.category",
            resIds: this.props.filters.categ_ids || [],
            domain: [],
            update: (ids) => this.props.onFilterChange({ categ_ids: ids }),
            placeholder: _t("Categorías"),
        };
    }
}
