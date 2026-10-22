# -*- coding: utf-8 -*-
# Part of Wicoders Solution. See LICENSE file for full copyright and licensing

{
    'name' : 'Purchase Advance Payment',
    'category': 'Purchases',
    'version': '19.0.1.0',
    'author': 'Wicoders Solutions',
    'description': """
        This module allows users to generate advance payments to suppliers based on purchase orders, streamlining the procurement and payment process.
    """,
    'summary': """This module allows registering supplier advance payments directly from purchase orders — simplifying purchase payment and PO advance payment processes.""",
    'depends' : ['base', 'purchase'],
    'price': 0,
    'currency': 'EUR',
    'license': 'AGPL-3',
    "author": "Wicoders Solutions",
    'website': 'https://wicoders.com/',
    'data': [
        'views/purchase_order.xml',
        'views/res_config_setting.xml',
    ],
    'demo': [],
    'images': ['static/description/banner.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
}

