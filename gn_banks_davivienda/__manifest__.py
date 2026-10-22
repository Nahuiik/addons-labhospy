# -*- coding: utf-8 -*-
{
    "name": "GN Importación liquidaciones Banco Davivienda POS",
    "version": "19.0.1.0.3",
    "category": "Accounting/Banks",
    "summary": "Importa Excel de liquidaciones Banco Davivienda y crea partidas GN Banks por día",
    "description": """Importador del reporte Excel de transacciones POS de Banco Davivienda a
documentos GN Banks (debit.credit). El reporte es transaccional (varias filas por día); las
filas se agrupan por FECHA_TRX y se genera una liquidación por día: NETO_DEPOSITO al banco,
IMPORTE_COMERCIO (comisión) y los impuestos retenidos a la cuenta de comisión POS.""",
    "author": "Grupo Nahuiik",
    "license": "LGPL-3",
    "depends": ["gn_banks", "account"],
    "external_dependencies": {"python": ["openpyxl"]},
    "data": [
        "security/ir.model.access.csv",
        "security/davivienda_import_history_rules.xml",
        "wizard/davivienda_import_wizard_views.xml",
        "views/davivienda_import_history_views.xml",
        "views/menu_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "gn_banks_davivienda/static/src/import_result/*.js",
            "gn_banks_davivienda/static/src/import_result/*.xml",
            "gn_banks_davivienda/static/src/import_result/*.scss",
        ],
    },
    "installable": True,
    "application": False,
}
