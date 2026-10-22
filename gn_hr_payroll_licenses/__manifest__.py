# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
{
    "name": "GN HR Payroll — Licencias de conducir (multi-país)",
    "summary": "Modelos hr.license.type y hr.employee.license sin reglas de nómina por país",
    "version": "19.0.1.0.7",
    "category": "Human Resources",
    "author": "Grupo Nahuiik",
    "license": "LGPL-3",
    "depends": [
        "hr",
        "l10n_hn_payroll_base",
    ],
    "data": [
        "security/gn_hr_payroll_licenses_security.xml",
        "security/ir.model.access.csv",
        "views/hr_license_views.xml",
    ],
    "installable": True,
    "application": False,
}
