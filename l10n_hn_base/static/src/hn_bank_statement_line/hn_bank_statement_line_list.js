/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";

/** Placeholder js_class for future bank-line list UX (notifications, batch hints). */
export class HnBankStatementLineListController extends ListController {}

registry.category("views").add("hn_bank_statement_line_list", {
    ...listView,
    Controller: HnBankStatementLineListController,
});
