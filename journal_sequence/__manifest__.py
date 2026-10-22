# -*- coding: utf-8 -*-
{
    'name': 'Journal Sequence',
    'version': '2.0.0',
    'author': 'Grupo Nahuiik',
    'website': 'http://gruponahuiik.com',
    'description': """
        Add sequence configuration for journal in odoo 18.
        Below are search tags.
        custom journal sequence, odoo 18 journal sequence, account journal sequence, account journal sequence odoo 18.
                    
    """,
    'summary': """
        Add sequence configuration for journal in odoo 18 same like previous odoo version.
    """,
    'depends': [
        'account',
    ],
    'data': [
        'views/account_journal_view.xml',
        'views/account_move_view.xml',
    ],
    "images": ['static/description/1.png'],

    'installable': True,
    'license': 'OPL-1',
    'currency': 'USD',
    'price': 19.99
}