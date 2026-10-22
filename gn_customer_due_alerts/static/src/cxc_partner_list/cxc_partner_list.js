/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { CxcPartnerListRenderer } from "./cxc_partner_list_renderer";

registry.category("views").add("cxc_partner_receivable_list", {
    ...listView,
    Renderer: CxcPartnerListRenderer,
});
