# -*- coding: utf-8 -*-

{
    "name": "Disable Update Quantity Feature",
    "version": "19.0.1.0.0",
    "category": "Inventory/Inventory",
    'summary': 'Restrict product quantity updates and label printing to authorized users',
    "description": """Prevent unauthorized users from changing product on-hand quantities or printing labels by restricting the relevant actions to a dedicated security group.""",
    'author': 'Apagen Solutions Pvt Ltd',
    'company': 'Apagen Solutions Pvt Ltd',
    'maintainer': 'Apagen Solutions Pvt Ltd',
    'website': "https://www.apagen.com",
    "depends": ["stock"],
    "data": [
        'security/product_security.xml',
        'views/product.xml',
    ],
    "assets": {
        "web.assets_backend": [
            "apg_disable_update_qty/static/src/forecasted_patch.js",
            "apg_disable_update_qty/static/src/xml/forecasted_buttons.xml",
        ],
    },
    "license": 'LGPL-3',
    "installable": True,
    "application": True,
    "auto_install": False,
    "images": ['static/description/banner.jpg'],
}
