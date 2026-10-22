# © 2025 Grupo Nahuiik
# See README.rst for license details.

{
    "name": "Honduras Payroll CE - Employee Salary Inputs (HN Base)",
    "summary": "Beneficios/deducciones por empleado, IHSS y AFP; sincroniza inputs con hr.payslip (l10n_hn_payroll_base)",
    "version": "19.0.1.0.1",
    "category": "Human Resources/Payroll",
    "author": "Grupo Nahuiik",
    "website": "https://www.gruponahuiik.com",
    "license": "LGPL-3",
    "depends": [
        "l10n_hn_payroll_base",
    ],
    "excludes": [
        "bi_hr_payroll",
        "bi_hr_payroll_account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/hr_payroll_data.xml",
        "views/hr_employee_views.xml",
        "views/hr_ihss_settings_views.xml",
        "views/hr_afp_settings_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
