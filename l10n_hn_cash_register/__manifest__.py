# -*- coding: utf-8 -*-
{
    'name': "Cash Register Report",
    'summary': "Arqueo de caja con impresión PDF/XLSX y control de cheques",
    'description': """
        Permite generar reportes de arqueo de caja con soporte para impresión PDF y XLSX,
        registrando información adicional como número y fecha de cheques en pagos aplicados.
    """,
    'author': "Nahuiik",
    'website': "https://www.gruponahuiik.com",
    'category': 'Accounting/Reporting',
    'version': '19.0.1.0.11',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'report_xlsx',
        'sale',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/paperformat.xml',
        'views/account_journal_view.xml',
        'views/account_payment_register_view.xml',
        'views/account_payment_view.xml',
        'wizard/cash_register_wizard.xml',
        'report/report_cash_register.xml',
        'report/report_report.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
