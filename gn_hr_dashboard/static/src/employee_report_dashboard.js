/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
import { Component, useState } from "@odoo/owl";
import { employeeReportCategoriesRegistry } from "./employee_report_registry";

export class EmployeeReportDashboard extends Component {
    static template = "gn_hr_dashboard.EmployeeReportDashboard";
    static components = { Layout };
    static props = ["*"];

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");
        const all = employeeReportCategoriesRegistry.getAll();
        this.reportCategories = Object.values(all).sort(
            (a, b) => (a.sequence ?? 99) - (b.sequence ?? 99)
        );
        this.state = useState({ searchTerm: "" });
    }

    get display() {
        return { controlPanel: {} };
    }

    get filteredReportCategories() {
        const q = (this.state.searchTerm || "").trim().toLowerCase();
        if (!q) {
            return this.reportCategories;
        }
        const out = [];
        for (const cat of this.reportCategories) {
            const labelHit = (cat.label || "").toLowerCase().includes(q);
            const reps = (cat.reports || []).filter((r) =>
                (r.label || "").toLowerCase().includes(q)
            );
            if (labelHit) {
                out.push(cat);
            } else if (reps.length) {
                out.push({ ...cat, reports: reps });
            }
        }
        return out;
    }

    uiStr(key) {
        const map = {
            wizard_full: _t("Wizard completo"),
            wizard_title: _t("Abrir wizard completo para seleccionar múltiples reportes"),
            search_ph: _t("Buscar informe…"),
            intro: _t(
                "Seleccione un informe para generar el reporte en Excel. Puede filtrar por empleados en el wizard que se abrirá."
            ),
            empty: _t(
                "No hay categorías de informes registradas. Instale un módulo de localización de nómina que las añada (p. ej. l10n_hn_hr_payroll)."
            ),
        };
        return map[key] || key;
    }

    openReport(actionXmlId) {
        this.actionService.doAction(actionXmlId);
    }

    async openFullWizard() {
        try {
            await this.actionService.doAction(
                "l10n_hn_hr_payroll.action_hr_employee_report_wizard"
            );
        } catch {
            this.notification.add(
                _t(
                    "El wizard de informes no está disponible. Instale el módulo de localización de nómina que lo define (por ejemplo l10n_hn_hr_payroll)."
                ),
                { type: "warning" }
            );
        }
    }
}
