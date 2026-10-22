{
    'name': 'Análisis Estados de Cuenta con OpenAI',
    'category': 'Accounting/Accounting',
    'version': '19.0.1.0.21',
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'summary': 'Importa estados de cuenta (QIF, XLS FICOHSA), detecta duplicados y sugiere modelos de conciliación con IA.',
    'license': 'OPL-1',
    'depends': [
        'account',
        'bus',
    ],
    'assets': {
        'web.assets_backend': [
            'gn_qif_openai_reconcile/static/src/gn_qif_progress_service.js',
            'gn_qif_openai_reconcile/static/src/js/qif_ai_import_progress.js',
            'gn_qif_openai_reconcile/static/src/xml/qif_ai_import_progress.xml',
        ],
    },
    'external_dependencies': {
        'python': ['openai', 'xlrd'],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/account_journal_gn_qif_views.xml',
        'views/qif_ai_wizard_views.xml',
        'views/gn_qif_import_history_views.xml',
        'views/gn_qif_journal_knowledge_views.xml',
        'views/gn_qif_suggestion_views.xml',
    ],
    'installable': True,
    'application': False,
}
