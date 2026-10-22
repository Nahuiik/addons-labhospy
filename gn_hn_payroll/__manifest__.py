{
    "name": "GN Honduras Payroll Employee Inputs",
    "summary": "Gestiona Salary Inputs desde la ficha del empleado y los sincroniza con la nomina.",
    "version": "19.0.1.0.2",
    "category": "Human Resources/Payroll",
    "author": "GN",
    "website": "https://www.gn.hn",
    "license": "LGPL-3",
    "depends": [
        "hr_payroll",
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
