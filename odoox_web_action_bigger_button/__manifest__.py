{
    'name': 'Enlarged & Comfortable Gear/Save/Discard Buttons',
    'summary': 'Enlarged form actions, save and discard buttons for better UX',
    'description': '''
        This module enlarges icon buttons to improvement user experience.
    ''',
    'version': '19.0.1.0',
    'category': 'Web',
    'author': 'OdooX.com',
    'company': 'OdooX Studio',
    'website': 'http://www.odoox.com',
    'maintainer': 'OdooX Studio',
    'live_test_url': '',
    'depends': [
        'web',
    ],
    'data': [
    ],
    'assets': {
        'web.assets_backend': [
            ('after', 'web/static/src/search/**/*', 'odoox_web_action_bigger_button/static/src/**/*'),
        ],
    },
    'images': [
        'static/description/banner.jpg',
    ],
    'price': 0,
    'currency': 'USD',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
