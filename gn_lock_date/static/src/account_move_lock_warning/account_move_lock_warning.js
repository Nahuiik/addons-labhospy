/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useBus, useService } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";

/**
 * Soft warning on account.move form when gn.period.lock would block the draft.
 * Hard validation remains on the server (create/write/action_post).
 */
patch(FormController.prototype, {
    setup() {
        super.setup();
        if (this.props.resModel !== "account.move") {
            return;
        }
        const orm = useService("orm");
        const notification = useService("notification");
        let lastClose = null;
        const check = debounce(async () => {
            const root = this.model.root;
            if (!root?.data) {
                return;
            }
            const date = root.data.date;
            let journalId = root.data.journal_id;
            if (Array.isArray(journalId)) {
                journalId = journalId[0];
            }
            let companyId = root.data.company_id;
            if (Array.isArray(companyId)) {
                companyId = companyId[0];
            }
            if (!date || !journalId) {
                return;
            }
            try {
                const moveIds = root.resId ? [root.resId] : [];
                const res = await orm.call("account.move", "gn_get_period_lock_status", [
                    moveIds,
                    date,
                    journalId,
                    companyId || false,
                ]);
                if (res.blocked && res.message) {
                    if (lastClose) {
                        lastClose();
                    }
                    lastClose = notification.add(res.message, {
                        type: "warning",
                        sticky: false,
                    });
                }
            } catch {
                /* Save/post still enforced in Python */
            }
        }, 450);
        useBus(this.model.bus, "update", check);
    },
});
