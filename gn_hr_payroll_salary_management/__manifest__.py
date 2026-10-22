# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

{
    "name": "Payroll Salary Management (shared)",
    "summary": "Aumentos salariales, historial de aumentos y anticipos (núcleo reutilizable HN/SV)",
    "version": "19.0.1.0.12",
    "post_init_hook": "post_init_hook",
    "category": "Human Resources/Payroll",
    "author": "Grupo Nahuiik",
    "license": "LGPL-3",
    "depends": [
        "mail",
        "l10n_hn_payroll_base",
        "account",
        "gn_hr_payroll_employee_extras",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/hr_salary_increase_views.xml",
        "views/salary_advance_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
