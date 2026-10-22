/** @odoo-module **/

import { registry } from "@web/core/registry";
import { SalesDashboardPremium } from "./sales_dashboard";

registry.category("actions").add("gn_sales_command_center", SalesDashboardPremium);
