# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name' : 'GTS COA',
    'version' : '19.0.1.0.10',
    'summary': 'GTS COA',
    'sequence': 30,
    'description': """ Chart of Accounts with hierarchy.
        This module create parent and child relation in account""",
    'category' : 'Accounting & Finance',
    'price': 19.99,
    'currency': 'EUR',
    'license': 'OPL-1',
    'author': 'Geo Technosoft',
    'website': 'http://www.geotechnosoft.com',
    'company': 'Geo Technosoft Solutions Pvt Ltd.',
    'depends' : ['account'],
    'data': [
        'security/gts_coa_hierarchy_security.xml',
        'security/ir.model.access.csv',
        'views/open_chart.xml',
        'views/report_coa_hierarchy.xml',
        'views/account_account_view.xml',
        'views/account_view.xml',
    ],
    'assets': {
        'web.assets_common': [
            'gts_coa_hierarchy/static/src/scss/coa_hierarchy.scss',
        ],
        'web.assets_backend': [
            'gts_coa_hierarchy/static/src/js/account_type_selection.js',
            'gts_coa_hierarchy/static/src/js/coa_report_backend.js',
            'gts_coa_hierarchy/static/src/xml/coa_report_backend.xml',
            'gts_coa_hierarchy/static/src/xml/coa_report_extra.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': '_init_parent_path',
}
