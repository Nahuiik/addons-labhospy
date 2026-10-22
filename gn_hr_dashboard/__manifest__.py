# -*- coding: utf-8 -*-
{
    "name": "GN HR Dashboard",
    "summary": "Dashboard unificado: informes de empleados y vista regional multi-compañía",
    "version": "19.0.1.0.17",
    "category": "Human Resources",
    "author": "Grupo Nahuiik <info@gruponahuiik.com>",
    "website": "https://www.gruponahuiik.com",
    "license": "LGPL-3",
    "depends": [
        "mail",
        "hr",
        "web",
        "l10n_hn_payroll_base",
        "hr_holidays",
    ],
    "data": [
        "security/groups.xml",
        "views/dashboard_actions.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "gn_hr_dashboard/static/src/employee_report_registry.js",
            "gn_hr_dashboard/static/src/employee_report_dashboard.scss",
            "gn_hr_dashboard/static/src/employee_report_dashboard.xml",
            "gn_hr_dashboard/static/src/employee_report_dashboard.js",
            "gn_hr_dashboard/static/src/regional_dashboard.scss",
            "gn_hr_dashboard/static/src/regional_dashboard.xml",
            "gn_hr_dashboard/static/src/regional_dashboard.js",
            "gn_hr_dashboard/static/src/main_dashboard.scss",
            "gn_hr_dashboard/static/src/main_dashboard.xml",
            "gn_hr_dashboard/static/src/main_dashboard.js",
        ],
    },
    "installable": True,
    "application": False,
}
