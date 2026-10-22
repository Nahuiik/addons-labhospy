# -*- coding: utf-8 -*-
{
    'name': 'Tablero Financiero (Dashboard)',
    'category': 'Accounting',
    'version': '19.0.19.2.0',
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'summary': (
        'Tablero visual de indicadores financieros (rentabilidad, liquidez, '
        'cartera y alertas) sobre la contabilidad. Complementa los reportes BI.'
    ),
    'license': 'OPL-1',
    'depends': ['account', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'security/dashboard_user_pref_rules.xml',
        'views/dashboard_config_views.xml',
        'views/dashboard_user_pref_views.xml',
        'views/dashboard_budget_views.xml',
        'views/dashboard_kpi_views.xml',
        'views/dashboard_benchmark_views.xml',
        'views/dashboard_alert_views.xml',
        'views/financial_dashboard_menu.xml',
        'data/benchmark_data.xml',
        'data/alert_rules_data.xml',
        'report/financial_executive_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            ('include', 'web.chartjs_lib'),
            'gn_financial_dashboard/static/src/dashboard/**/*.js',
            'gn_financial_dashboard/static/src/dashboard/**/*.xml',
            'gn_financial_dashboard/static/src/dashboard/**/*.scss',
        ],
    },
    'installable': True,
    'application': True,
}
