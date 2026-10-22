/** @odoo-module **/

import { employeeReportCategoriesRegistry } from "@gn_hr_dashboard/employee_report_registry";

employeeReportCategoriesRegistry.add(
    "personal",
    {
        id: "personal",
        label: "Datos personales",
        icon: "fa-user",
        color: "#0d6efd",
        sequence: 10,
        reports: [
            {
                action: "l10n_hn_hr_payroll.action_hr_employee_report_tallas",
                label: "Tallas",
                icon: "fa-shirtsinbulk",
            },
            {
                action: "l10n_hn_hr_payroll.action_hr_employee_report_emergency",
                label: "Contactos de emergencia",
                icon: "fa-phone",
            },
            {
                action: "l10n_hn_hr_payroll.action_hr_employee_report_birthdays",
                label: "Cumpleaños",
                icon: "fa-birthday-cake",
            },
            {
                action: "l10n_hn_hr_payroll.action_hr_employee_report_family",
                label: "Datos familiares",
                icon: "fa-users",
            },
            {
                action: "l10n_hn_hr_payroll.action_hr_employee_report_beneficiaries",
                label: "Beneficiarios",
                icon: "fa-handshake-o",
            },
            {
                action: "l10n_hn_hr_payroll.action_hr_employee_report_health_status",
                label: "Estado de salud",
                icon: "fa-heartbeat",
            },
        ],
    },
    { sequence: 10 }
);

employeeReportCategoriesRegistry.add(
    "documents",
    {
        id: "documents",
        label: "Documentos",
        icon: "fa-folder-open",
        color: "#198754",
        sequence: 20,
        reports: [
            {
                action: "l10n_hn_hr_payroll.action_hr_employee_report_licenses",
                label: "Licencias de conducir",
                icon: "fa-id-card",
            },
            {
                action: "l10n_hn_hr_payroll.action_hr_employee_report_documents",
                label: "Documentos de entrada",
                icon: "fa-file",
            },
            {
                action: "l10n_hn_hr_payroll.action_hr_employee_report_references",
                label: "Referencias",
                icon: "fa-address-book",
            },
        ],
    },
    { sequence: 20 }
);

employeeReportCategoriesRegistry.add(
    "contracts",
    {
        id: "contracts",
        label: "Contratos y nómina",
        icon: "fa-briefcase",
        color: "#6f42c1",
        sequence: 30,
        reports: [
            {
                action: "l10n_hn_hr_payroll.action_hr_employee_list_l10n_hn",
                label: "Listado de empleados",
                icon: "fa-list",
            },
            {
                action: "l10n_hn_hr_payroll.action_hr_employee_export_excel_wizard",
                label: "Registro de contratos",
                icon: "fa-file-excel-o",
            },
            {
                action: "l10n_hn_hr_payroll.action_hr_employee_report_contracts",
                label: "Reporte de contratos",
                icon: "fa-file-text",
            },
            {
                action: "l10n_hn_hr_payroll.action_hr_employee_report_salary_increases",
                label: "Historial de aumentos",
                icon: "fa-line-chart",
            },
            {
                action: "l10n_hn_hr_payroll.action_hr_employee_report_seniority",
                label: "Antigüedad",
                icon: "fa-calendar",
            },
            {
                action: "l10n_hn_hr_payroll.action_hr_employee_report_loans",
                label: "Préstamos",
                icon: "fa-money",
            },
            {
                action: "gn_hr_payroll_employee_extras.action_hr_recurring_concept_report",
                label: "Reporte de conceptos recurrentes",
                icon: "fa-refresh",
            },
        ],
    },
    { sequence: 30 }
);

employeeReportCategoriesRegistry.add(
    "organization",
    {
        id: "organization",
        label: "Organización",
        icon: "fa-sitemap",
        color: "#fd7e14",
        sequence: 40,
        reports: [
            {
                action: "l10n_hn_hr_payroll.action_hr_employee_report_headcount",
                label: "Headcount",
                icon: "fa-bar-chart",
            },
            {
                action: "l10n_hn_hr_payroll.action_hr_parent_children_report",
                label: "Padres, Madres e Hijos",
                icon: "fa-child",
            },
        ],
    },
    { sequence: 40 }
);

employeeReportCategoriesRegistry.add(
    "alerts",
    {
        id: "alerts",
        label: "Alertas y seguimiento",
        icon: "fa-bell",
        color: "#dc3545",
        sequence: 50,
        reports: [
            {
                action: "l10n_hn_hr_payroll.action_hr_employee_report_warnings",
                label: "Empleados con alertas",
                icon: "fa-exclamation-triangle",
            },
            {
                action: "l10n_hn_hr_payroll.action_hr_employee_report_trial_period",
                label: "Período de prueba",
                icon: "fa-hourglass-half",
            },
            {
                action: "l10n_hn_hr_payroll.action_hr_employee_report_hires_departures",
                label: "Altas y Bajas",
                icon: "fa-exchange",
            },
        ],
    },
    { sequence: 50 }
);

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
                action: "l10n_hn_hr_payroll.action_hr_employee_report_skills",
                label: "Inventario de habilidades",
                icon: "fa-star",
            },
            {
                action: "l10n_hn_hr_payroll.action_hr_employee_report_certifications",
                label: "Certificaciones",
                icon: "fa-certificate",
            },
            {
                action: "l10n_hn_hr_payroll.action_hr_employee_report_resume",
                label: "Currículum",
                icon: "fa-file-text-o",
            },
        ],
    },
    { sequence: 45 }
);
