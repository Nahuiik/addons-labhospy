# -*- coding: utf-8 -*-
{
    "name": "Arqueo de Caja Diario",
    "version": "19.0.1.0.0",
    "author": "Grupo Nahuiik",
    'website': 'https://www.gruponahuiik.com',
    "category": "Accounting/Reporting",
    "license": "LGPL-3",
    'summary': 'Reporte de Arqueo de Caja',
    'description': """
        Reporte de Arqueo de Caja para Odoo 19
        Genera reportes de arqueo de caja en formato Excel
    """,
    'depends': [
        'account',
        'report_xlsx',
    ],
    'data': [
        'security/groups.xml',
        'views/journal_view_inh.xml',
        'wizard/cash_settlement_view.xml',
        'report/report_reports.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
