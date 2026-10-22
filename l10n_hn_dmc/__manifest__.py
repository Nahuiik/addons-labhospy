# -*- coding: utf-8 -*-
{
    "name": "Reporte DMC",
    "summary": "Exportación XLS del reporte DMC (compras / facturas proveedor).",
    "description": "Asistente y reporte Excel para el formato DMC sobre facturas de proveedor. "
                   "El menú se agrupa bajo Contabilidad → Honduras (SAR / fiscal), junto al 904 y libros.",
    "author": "Grupo Nahuiik",
    "website": "https://www.gruponahuiik.com/",
    "category": "Accounting/Localizations",
    "version": "19.0.1.1.1",
    "license": "OPL-1",
    "depends": [
        "base",
        "account",
        "report_xlsx",
        "l10n_hn_account",
        "l10n_hn_reports",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizard/wizard_dmc.xml",
    ],
    "installable": True,
    "application": False,
}
