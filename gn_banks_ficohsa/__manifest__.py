# -*- coding: utf-8 -*-
{
    "name": "GN Importación liquidaciones FICOHSA POS",
    "version": "19.0.1.0.3",
    "category": "Accounting/Banks",
    "summary": "Importa Excel «Cierre por Terminal» de FICOHSA y crea liquidaciones GN Banks por día",
    "description": """Importador del reporte Excel «Cierre por Terminal» de FICOHSA (VISANET) a
documentos GN Banks (debit.credit). Por cada archivo se agrupan las transacciones por
Fecha de Pago y se genera una liquidación por día.""",
    "author": "Grupo Nahuiik",
    "license": "LGPL-3",
    "depends": ["gn_banks", "account"],
    "external_dependencies": {"python": ["openpyxl"]},
    "data": [
        "security/ir.model.access.csv",
        "security/ficohsa_import_history_rules.xml",
        "wizard/ficohsa_import_wizard_views.xml",
        "views/ficohsa_import_history_views.xml",
        "views/menu_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "gn_banks_ficohsa/static/src/import_result/*.js",
            "gn_banks_ficohsa/static/src/import_result/*.xml",
            "gn_banks_ficohsa/static/src/import_result/*.scss",
        ],
    },
    "installable": True,
    "application": False,
}
