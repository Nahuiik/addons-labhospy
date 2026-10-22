# -*- coding: utf-8 -*-
{
    "name": "GN Importación liquidaciones BAC POS",
    "version": "19.0.1.1.0",
    "category": "Accounting/Banks",
    "summary": "Importa CSV de liquidaciones BAC Credomatic y crea partidas GN Banks por día",
    "description": """Importador CSV BAC Credomatic a documentos GN Banks (debit.credit).
Agrupa por día y genera una liquidación por cada fecha con movimiento.""",
    "author": "Grupo Nahuiik",
    "license": "LGPL-3",
    "depends": ["gn_banks", "account"],
    "data": [
        "security/ir.model.access.csv",
        "security/bac_import_history_rules.xml",
        "wizard/bac_import_wizard_views.xml",
        "views/bac_import_history_views.xml",
        "views/menu_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "gn_banks_pos/static/src/import_result/*.js",
            "gn_banks_pos/static/src/import_result/*.xml",
            "gn_banks_pos/static/src/import_result/*.scss",
        ],
    },
    "installable": True,
    "application": False,
}
