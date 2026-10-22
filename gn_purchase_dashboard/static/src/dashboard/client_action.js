/** @odoo-module **/

import { registry } from "@web/core/registry";
import { PurchaseDashboardPremium } from "./purchase_dashboard";

registry.category("actions").add("gn_purchase_command_center", PurchaseDashboardPremium);
