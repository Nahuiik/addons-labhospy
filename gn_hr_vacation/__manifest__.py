# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

{
    "name": "Vacaciones y ausencias (base)",
    "summary": "Planes de vacaciones (reglas por antigüedad), tipo principal de vacaciones anuales y extensión base en ausencias; menús y reglas de nómina por país van en otros módulos.",
    "version": "19.0.1.0.19",
    "category": "Human Resources/Time Off",
    "author": "Grupo Nahuiik",
    "website": "https://www.gruponahuiik.com",
    "license": "LGPL-3",
    "depends": [
        "hr_holidays",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/gn_vacation_plan_security.xml",
        "views/gn_vacation_plan_views.xml",
        "views/hr_leave_type_views.xml",
        "wizard/gn_collective_vacation_wizard_views.xml",
        "wizard/gn_collective_vacation_result_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "gn_hr_vacation/static/src/vacation/collective_vacation_wizard/collective_vacation_preview.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": [],
}
