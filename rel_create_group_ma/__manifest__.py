# -*- coding: utf-8 -*-
{
    'name': 'Hide Quick Create Many2x',
    'version': '19.0.1.0',
    'category': 'Extra Tools',
    'summary': """Hide create and edit option based on user group""",
    'description': """ Updates Below
    - Added new group to quick create m2x
    - Create and create edit based on user
    """,
    'author': 'Mohammed Amal',
    'maintainer': 'Mohammed Amal',
    'depends': [
        'base',
    ],
    'data': [
        'security/res_groups.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'rel_create_group_ma/static/src/**/*',
        ],

    },
    'images': ['static/description/banner.png'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
