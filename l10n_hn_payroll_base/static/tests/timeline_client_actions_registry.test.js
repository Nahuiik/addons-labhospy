/** @odoo-module */

import { describe, expect, test } from "@odoo/hoot";
import { registry } from "@web/core/registry";

describe.current.tags("desktop");

describe("l10n_hn_payroll_base timeline client actions", () => {
    test("hn_holidays_timeline_ce is registered", () => {
        expect(registry.category("actions").contains("hn_holidays_timeline_ce")).toBe(true);
    });

    test("hn_holidays_timeline_oss is registered", () => {
        expect(registry.category("actions").contains("hn_holidays_timeline_oss")).toBe(true);
    });
});
