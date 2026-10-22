# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Odoo Direct Print',
    'version': '19.0.0.0',
    'category': '',
    'summary': '',
    'description': """ """,
    'author': 'BROWSEINFO',
    'website': "https://www.browseinfo.com",
    'depends': ['base','web'],
    'data': [
        'views/ir_actions_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bi_odoo_direct_print/static/src/js/print_popup_report.js',

        ]
    },
    'installable': True,
    'license': 'OPL-1',
    "auto_install": False,
    'live_test_url': 'https://www.browseinfo.com',
}
