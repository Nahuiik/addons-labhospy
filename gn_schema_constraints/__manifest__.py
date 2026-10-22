{
    "name": "GN Schema Constraints",
    "summary": "Normaliza datos y agrega restricciones NOT NULL para campos requeridos.",
    "version": "19.0.1.0.0",
    "category": "Technical Settings",
    "author": "GN",
    "website": "https://www.gn.hn",
    "license": "LGPL-3",
    "depends": [
        "calendar",
        "gn_hn_payroll",
    ],
    "data": [],
    "installable": True,
    "application": False,
    "auto_install": False,
    "post_init_hook": "ensure_not_null_constraints",
}
