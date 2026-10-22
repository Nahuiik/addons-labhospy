# Copyright 2025 Digital Wave Solutions
# Website: https://www.dwave-s.com/
# Email: info@dwave-s.com
# Phone:00249900034328 - 00256754893624

{
    "name": "Dwave Refresh Button",
    'version': '2.0.1',
    "summary": "Add a refresh button in the top bar to reload the Odoo client.",
    "description": """
Dwave Refresh Button
=======================
This module adds a refresh button in the Odoo backend top bar (next to the notifications and user menu).

📱 Especially useful on Odoo Mobile:
- Apply backend changes without logging out/in
- Refreshes the full client session

Features
--------
- Instantly refresh the current Odoo session with a single click.
- Designed for seamless integration in both mobile and desktop environments.

""",
    'category': 'Usability',
	'author': 'Digital Wave Solutions',
	'support' : 'info@dwave-s.com',
    'website' : 'https://www.dwave-s.com/',
    "depends": ["web"],
    "assets": {
        "web.assets_backend": [
            "dwave_refresh_button/static/src/js/refresh_button.js",
            "dwave_refresh_button/static/src/xml/refresh_button.xml",
            "dwave_refresh_button/static/src/scss/refresh_button.scss",
        ],
    },
    
    'images': ["static/description/icon.png", "static/description/banner.png", "images/refresh_button.png"],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
