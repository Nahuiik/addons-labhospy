# -*- coding: utf-8 -*-
{
    'name': 'Balances de diarios banco',
    'category': 'Accounting',
    'version': '19.0.1.0.27',
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'summary': (
        'Balances bancarios: snapshot de saldos y dashboard semanal de liquidez (OWL).'
    ),
    'license': 'OPL-1',
    'depends': ['account', 'web', 'gn_banks'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_journal_views.xml',
        'views/bank_balance_menu.xml',
        'views/weekly_balance_dashboard_views.xml',
        'wizard/weekly_balance_report_views.xml',
        'reports/weekly_balance_report_templates.xml',
        'reports/weekly_balance_reports.xml',
    ],
    'assets': {
        'web.assets_backend': [
            ('include', 'web.chartjs_lib'),
            'gn_banks_balance/static/src/weekly_balance_dashboard/**/*.js',
            'gn_banks_balance/static/src/weekly_balance_dashboard/**/*.xml',
            'gn_banks_balance/static/src/weekly_balance_dashboard/**/*.scss',
        ],
    },
    'installable': True,
    'application': False,
}
