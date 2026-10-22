# -*- coding: utf-8 -*-
{
    'name': 'Banks UI — Modern Treasury Experience',
    'category': 'Accounting',
    'version': '19.0.1.0.30',
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'summary': 'Modern OWL-based UI for bank operations: workflow, dashboard, kanban and premium forms.',
    'license': 'OPL-1',
    'depends': [
        'gn_banks',
        'gn_banks_balance',
        'web',
        'mail',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/debit_credit_views.xml',
        'views/bank_transfer_views.xml',
        'views/bank_check_views.xml',
        'views/kanban_views.xml',
        'views/search_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'gn_banks_ui/static/src/scss/*.scss',
            'gn_banks_ui/static/src/js/**/*.js',
            'gn_banks_ui/static/src/xml/**/*.xml',
        ],
    },
    'installable': True,
    'application': False,
    'post_init_hook': 'post_init_hook',
}
