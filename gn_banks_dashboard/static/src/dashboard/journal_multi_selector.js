/** @odoo-module **/

import { Component, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { TagsList } from "@web/core/tags_list/tags_list";
import { RecordAutocomplete } from "@web/core/record_selectors/record_autocomplete";
import { useTagNavigation } from "@web/core/record_selectors/tag_navigation_hook";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { journalSelectorLabels } from "./dashboard_labels";

/** Show 3 tags + "+N" (TagsList uses visibleItemsLimit - 1 visible tags). */
const VISIBLE_ITEMS_LIMIT = 4;

export class GnBanksJournalMultiSelector extends Component {
    static template = "gn_banks_dashboard.GnBanksJournalMultiSelector";
    static components = { TagsList, RecordAutocomplete };
    static props = {
        resIds: { type: Array, element: Number },
        companyId: { type: Number },
        allJournalIds: { type: Array, element: Number, optional: true },
        journalMeta: { type: Object, optional: true },
        onUpdate: Function,
    };

    setup() {
        this.nameService = useService("name");
        this.tags = [];
        useTagNavigation("journalSelector", {
            delete: (index) => this.deleteTag(index),
        });
        onWillStart(() => this.computeTags());
        onWillUpdateProps((nextProps) => this.computeTags(nextProps));
    }

    get journalDomain() {
        return [
            ["type", "in", ["bank", "cash"]],
            ["company_id", "=", this.props.companyId],
        ];
    }

    get labels() {
        return journalSelectorLabels();
    }

    get placeholder() {
        return this.tags.length ? "" : this.labels.searchPlaceholder;
    }

    get selectionSummary() {
        const selected = this.props.resIds.length;
        const total = (this.props.allJournalIds || []).length;
        if (!total) {
            return _t("No journals available");
        }
        if (selected === 0) {
            return _t("All journals (no filter)");
        }
        if (selected === total) {
            return _t("All journals (%s)", total);
        }
        return _t("%s of %s journals", selected, total);
    }

    journalBankName(journalId) {
        return this.props.journalMeta?.[journalId]?.bank_name || "";
    }

    async computeTags(props = this.props) {
        const displayNames = await this.nameService.loadDisplayNames(
            "account.journal",
            props.resIds
        );
        this.tags = props.resIds.map((id, index) => ({
            text: displayNames[id] || _t("Journal #%s", id),
            onDelete: () => this.deleteTag(index),
        }));
    }

    deleteTag(index) {
        const next = [
            ...this.props.resIds.slice(0, index),
            ...this.props.resIds.slice(index + 1),
        ];
        this.props.onUpdate(next);
    }

    update(resIds) {
        const merged = [...new Set([...this.props.resIds, ...resIds])];
        this.props.onUpdate(merged);
    }

    getIds() {
        return this.props.resIds;
    }

    onSelectAll() {
        const all = this.props.allJournalIds || [];
        this.props.onUpdate([...all]);
    }

    onClear() {
        this.props.onUpdate([]);
    }

    get visibleItemsLimit() {
        return VISIBLE_ITEMS_LIMIT;
    }

    get fieldString() {
        return this.labels.fieldString;
    }
}
