# -*- coding: utf-8 -*-
# Copyright 2025 Sveltware Solutions

{
    'name': 'Omux View Action',
    'category': 'Hidden',
    'version': '1.0.4',
    'license': 'OPL-1',
    'author': 'Sveltware Solutions',
    'website': 'https://www.linkedin.com/in/sveltware',
    'images': [
        'static/description/banner.png',
    ],
    'depends': ['omux_state_manager'],
    'assets': {
        'web.assets_backend': [
            (
                'before',
                'web/static/src/webclient/**/*',
                'omux_view_action/static/src/control_panel.xml',
            ),
            'omux_view_action/static/src/*.js',
            'omux_view_action/static/src/*.scss',
        ]
    },
}
