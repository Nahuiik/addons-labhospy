# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

{
    "name": "GN HR Employee Warnings (catálogo compartido)",
    "summary": "Tipos de alerta de empleado y panel de avisos reutilizable (HN/SV)",
    "version": "19.0.1.0.8",
    "category": "Human Resources",
    "author": "Grupo Nahuiik",
    "license": "LGPL-3",
    "depends": [
        "hr",
        "l10n_hn_payroll_base",
        "gn_hr_payroll_licenses",
        "gn_hr_payroll_employee_extras",
        "gn_hr_payroll_salary_management",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/hr_employee_warning_type_data.xml",
        "data/hr_employee_warning_type_missing_bank_account.xml",
        "views/hr_employee_warning_type_views.xml",
        "views/hr_employee_kanban_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
