# -*- coding: utf-8 -*-
{
    "name": "Auditoría de Diarios y Secuencias",
    "summary": "Mejora el chatter de los diarios contables: registra quién crea, "
               "modifica o elimina las secuencias y los cambios de configuración del diario.",
    "category": "Accounting",
    "version": "19.0.1.2.0",
    "author": "Grupo Nahuiik",
    "website": "https://www.gruponahuiik.com",
    "license": "OPL-1",
    "depends": [
        "account",
        "mail",
        "gn_banks",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/gn_audit_log_views.xml",
        "views/account_journal_views.xml",
    ],
    "installable": True,
    "application": False,
}
