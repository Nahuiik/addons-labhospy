/** @odoo-module **/

import { registry } from "@web/core/registry";
import { InvoicePaymentDashboard } from "./invoice_payment_dashboard";

registry.category("actions").add(
    "gn_accounting_invoice_payment_report",
    InvoicePaymentDashboard
);
