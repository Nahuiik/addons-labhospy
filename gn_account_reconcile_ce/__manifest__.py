{
    'name': 'Conciliación bancaria CE (Nahuiik)',
    'summary': 'Pipeline de matching inteligente y workspace OWL (servicio, estado reactivo, lista virtual) sin Enterprise.',
    'version': '19.0.1.0.2',
    'license': 'LGPL-3',
    'author': 'Grupo Nahuiik',
    'category': 'Accounting/Accounting',
    'depends': [
        'account',
        'account_statement_base',
        'web',
    ],
    'external_dependencies': {
        'python': ['rapidfuzz'],
    },
    'data': [
        'views/gn_account_reconcile_ce_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'gn_account_reconcile_ce/static/src/reconcile_ce/gn_ce_reconcile_client_action.xml',
            'gn_account_reconcile_ce/static/src/reconcile_ce/gn_account_reconcile_ce_service.js',
            'gn_account_reconcile_ce/static/src/reconcile_ce/gn_ce_reconcile_client_action.js',
        ],
    },
    'installable': True,
    'application': False,
}
