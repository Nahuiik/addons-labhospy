/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { GnQifBankStLineListController } from "./gn_qif_bank_st_line_list_controller";

registry.category("views").add("gn_qif_bank_st_line", {
    ...listView,
    Controller: GnQifBankStLineListController,
});
