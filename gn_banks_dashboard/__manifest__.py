# -*- coding: utf-8 -*-
{
    'name': 'Dashboard de Tesorería',
    'category': 'Accounting',
    'version': '19.0.1.0.29',
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'summary': 'Dashboard OWL de tesorería para operaciones gn_banks.',
    'license': 'OPL-1',
    'description': """
Dashboard interactivo de tesorería: KPIs, flujo de caja, distribuciones,
alertas operativas, riesgo, insights y drill-down a documentos gn_banks.
    """,
    'depends': ['account', 'web', 'gn_banks', 'gts_branch_management'],
    'data': [
        'security/ir.model.access.csv',
        'views/dashboard_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            ('include', 'web.chartjs_lib'),
            'gn_banks_dashboard/static/src/dashboard/**/*.js',
            'gn_banks_dashboard/static/src/dashboard/**/*.xml',
            'gn_banks_dashboard/static/src/dashboard/**/*.scss',
        ],
    },
    'installable': True,
    'application': False,
}
