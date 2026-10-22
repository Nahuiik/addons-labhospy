/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";

export class HnAccountMoveLineListController extends ListController {}

registry.category("views").add("hn_account_move_line_list", {
    ...listView,
    Controller: HnAccountMoveLineListController,
});
