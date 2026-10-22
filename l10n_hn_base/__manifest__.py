# -*- coding: utf-8 -*-
{
    'name': 'Honduras Base — Accountant UI',
    'version': '19.0.1.0.2',
    'summary': 'Bank statement lines, dashboard shortcuts, audit helpers (Community only)',
    'category': 'Accounting/Localizations',
    'author': 'Grupo Nahuiik',
    'license': 'LGPL-3',
    'website': 'https://www.gruponahuiik.com',
    'depends': [
        'account',
        'l10n_hn_account',
    ],
    'data': [
        'views/account_bank_statement_line_views.xml',
        'views/account_bank_statement_views.xml',
        'views/account_journal_dashboard_views.xml',
        'views/hn_bank_rec_actions_menus.xml',
        'views/account_move_views.xml',
        'views/mail_message_audit_views.xml',
        'views/hn_accountant_hub_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_hn_base/static/src/hn_accountant_hub/hn_accountant_hub.scss',
            'l10n_hn_base/static/src/hn_accountant_hub/hn_accountant_hub.js',
            'l10n_hn_base/static/src/hn_accountant_hub/hn_accountant_hub.xml',
            'l10n_hn_base/static/src/hn_bank_statement_line/hn_bank_statement_line_list.js',
            'l10n_hn_base/static/src/hn_bank_statement_line/hn_bank_rec_kanban.js',
            'l10n_hn_base/static/src/hn_account_move_line/hn_account_move_line_list.js',
        ],
    },
    'installable': True,
    'application': False,
}
