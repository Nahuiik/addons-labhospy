/** @odoo-module **/

import { employeeReportCategoriesRegistry } from "@gn_hr_dashboard/employee_report_registry";

employeeReportCategoriesRegistry.add(
    "vacations",
    {
        id: "vacations",
        label: "Vacaciones",
        icon: "fa-umbrella-beach",
        color: "#0dcaf0",
        sequence: 45,
        reports: [
            {
                action: "l10n_hn_hr_payroll.action_gn_hn_vacation_libro",
                label: "Libro de vacaciones",
                icon: "fa-book",
            },
            {
                action: "l10n_hn_hr_payroll.action_hn_vacation_report_by_dept_project",
                label: "Reporte por departamento, asignación, proyecto",
                icon: "fa-sitemap",
            },
            {
                action: "l10n_hn_hr_payroll.action_hn_approval_delegations_tree",
                label: "Reporte de delegaciones",
                icon: "fa-user-plus",
            },
        ],
    },
    { sequence: 45 }
);
