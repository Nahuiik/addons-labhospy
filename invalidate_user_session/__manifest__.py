# -*- coding: utf-8 -*-
{
    'name': 'Invalidate User Session',
    'version': '1.0',
    'summary': """Action to force user to logout during running session, only for administrator of the system.""",
    'description': """Action to force user to logout during running session, only for administrator of the system. """,
    'category': 'Extra Tools',
    'author': 'OMAR-NABIL',
    'license': 'AGPL-3',
    "images": ["static/description/banner.png"],
    'depends': ['base'],
    'data': [
        'data/ir_server.xml',
        'views/res_users_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'invalidate_user_session/static/src/js/**/*',
        ]
    },
    "license": "OPL-1",
    'installable': True,
    'auto_install': False,
    'application': False,
}
