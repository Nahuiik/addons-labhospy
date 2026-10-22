/** @odoo-module */

import { patch } from '@web/core/utils/patch';
import { Many2XAutocomplete } from "@web/views/fields/relational_utils";

import { _t } from "@web/core/l10n/translation";

patch(Many2XAutocomplete.prototype, {

    async suggest(request, lock) {
        const suggestions = [];
        /** @type {Record<string, any>[] | null} */
        let records = null;

        if (request.length < this.props.searchThreshold) {
            if (this.addStartTypingSuggestion({ request, records })) {
                suggestions.push(this.buildStartTypingSuggestion());
            }
        } else {
            records = await lock(this.search(request));
            if (records.length) {
                for (const record of records) {
                    suggestions.push(this.buildRecordSuggestion(request, record));
                }
            } else if (this.addNoRecordsSuggestion({ request, records })) {
                suggestions.push(this.buildNoRecordsSuggestion());
            } else if (this.addStartTypingSuggestion({ request, records })) {
                suggestions.push(this.buildStartTypingSuggestion());
            }
        }

        var has_create_group = await this.orm.call("res.users", "cur_user_has_group_js", ['rel_create_group_ma.group_create_mto'])
        for (const action of this.actionSuggestions) {
            if (!["bound buildCreateSuggestion", "bound buildCreateEditSuggestion"].includes(action.build.name)) {
                has_create_group = true
            }

            const enabled = action.enabled ?? (() => true);
            if (enabled({ request, records }) && has_create_group) {
                suggestions.push(action.build(request));
            }
        }

        return suggestions;
    }

});
