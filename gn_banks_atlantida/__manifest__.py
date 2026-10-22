# -*- coding: utf-8 -*-
{
    "name": "GN Importación liquidaciones Banco Atlántida POS",
    "version": "19.0.1.0.3",
    "category": "Accounting/Banks",
    "summary": "Importa Excel de liquidaciones Banco Atlántida y crea partidas GN Banks por día",
    "description": """Importador del reporte Excel de facturación POS de Banco Atlántida a
documentos GN Banks (debit.credit). Cada fila representa un día (columna FECHA); se genera
una liquidación por día: NETO A PAGAR al banco, TOTAL COMISION e ISV PAGAR SAR a la cuenta de
comisión POS.""",
    "author": "Grupo Nahuiik",
    "license": "LGPL-3",
    "depends": ["gn_banks", "account"],
    "external_dependencies": {"python": ["openpyxl"]},
    "data": [
        "security/ir.model.access.csv",
        "security/atlantida_import_history_rules.xml",
        "wizard/atlantida_import_wizard_views.xml",
        "views/atlantida_import_history_views.xml",
        "views/menu_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "gn_banks_atlantida/static/src/import_result/*.js",
            "gn_banks_atlantida/static/src/import_result/*.xml",
            "gn_banks_atlantida/static/src/import_result/*.scss",
        ],
    },
    "installable": True,
    "application": False,
}
