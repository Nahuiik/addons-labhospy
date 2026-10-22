# -*- coding: utf-8 -*-
{
    'name': "PS Report Invoice",
    'summary': """
        Reporte modulo de contabilidad
        """,
    'description': """
        Reporte modulo de contabilidad, estilo de factura de punto de ventas
    """,
    'author': "Grupo Nahuiik",
    'website': "https://www.ygruponahuiik.com",
    'category': 'Reporting',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'account',
        'l10n_hn_account',
    ],
    'data': [
        'views/account_move.xml',
        'data/paper_format.xml',
        'report/report_invoice_point_sale.xml',
        'report/report_report.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
