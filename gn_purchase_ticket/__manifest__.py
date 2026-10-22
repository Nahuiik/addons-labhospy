# -*- coding: utf-8 -*-

{
    'name': 'Boletas de Compra',
    # 'category': 'account',
    'version': '19.0.1.0.0',
    'icon': '/account/static/description/l10n.png',
    'author': 'Mario Matamoros - Grupo Nahuiik',
    'website': 'http://gruponahuiik.com',
    'summary': "Purchase Ticket",
    'license': 'OPL-1',
    'description':
        """  Purchase Ticket
        """,
    'depends': ['base', 'account', 'gn_banks', 'l10n_hn_account'],
    # 'auto_install': True,
    'data': [
        'views/account_journal_view.xml',
        'views/ir_sequence_view.xml',
        'views/purchase_ticket_view.xml',
        'data/paperformat.xml',
        'report/purchase_ticket_report.xml',
        'report/report_report.xml',
        'report/check_report.xml',
        'report/template_nahuiik_original.xml',
    ],

    'installable': True,
    'application': False,
}
