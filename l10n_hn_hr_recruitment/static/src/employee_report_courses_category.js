/** @odoo-module **/

import { employeeReportCategoriesRegistry } from "@gn_hr_dashboard/employee_report_registry";

try {
    const existing = employeeReportCategoriesRegistry.get("education");
    existing.reports.push({
        action: "gn_hr_recruitment_core.action_hr_employee_report_courses",
        label: "Cursos y Capacitaciones",
        icon: "fa-book",
    });
} catch {
    employeeReportCategoriesRegistry.add(
        "education",
        {
            id: "education",
            label: "Educación y formación",
            icon: "fa-graduation-cap",
            color: "#20c997",
            sequence: 45,
            reports: [
                {
                    action: "gn_hr_recruitment_core.action_hr_employee_report_courses",
                    label: "Cursos y Capacitaciones",
                    icon: "fa-book",
                },
            ],
        },
        { sequence: 45 }
    );
}
