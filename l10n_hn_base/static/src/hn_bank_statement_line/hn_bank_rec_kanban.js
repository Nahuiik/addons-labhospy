/** @odoo-module **/

import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanController } from "@web/views/kanban/kanban_controller";

/** Kanban entry for bank reconciliation; extends core Kanban for future panel UX. */
export class HnBankRecKanbanController extends KanbanController {}

registry.category("views").add("hn_bank_rec_kanban", {
    ...kanbanView,
    Controller: HnBankRecKanbanController,
});
