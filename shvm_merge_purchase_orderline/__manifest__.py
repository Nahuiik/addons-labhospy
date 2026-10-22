# -*- coding: utf-8 -*-
# Email: sales@creyox.com
{
    'name': "Auto Merge Duplicate Purchase Order Line | Manual Merge Duplicate Purchase Order Line",
    "author": "Creyox Technologies",
    'category': 'Purchases',
    'version': '19.0.0.0',
    'price': 0,
    'currency': 'USD',
    'summary': "User can merge the same product line in Purchase order by automatic or with use of button.",
    'description':
        """Merge the duplicate Purchase order line.""",
    "license": "LGPL-3",
    'depends': ['purchase'],
    'data': [
        'views/purchase_order_views.xml',
        'views/res_config_setting.xml',
    ],
    'demo': [],
    'images': [
        'static/description/banner.png'
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
