# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Sitaram Solutions (<https://sitaramsolutions.in/>).
#
#    For Module Support : info@sitaramsolutions.in  or Skype : contact.hiren1188
#
##############################################################################

{
    "name": "Cancel Validated Inventory Adjustment",
    "version": "19.0.0.0.1",
    "category": "Warehouse",
    "license": "OPL-1",
    "summary": 'This application will help user to rectify the mistake while importing or added product stocks though inventory adjustment. This application allow users to cancel inventory adjustment and delete all the related stock move. If you have enabled inventory valuation "Automated" then this app will also cancel stock accounting entry. Product quantity, quants and accounting entries are managed properly.',
    "description": """
    This application will help user to rectify the mistake while importing or added product stocks though inventory adjustment. This application allow users to cancel inventory adjustment and delete all the related stock move. If you have enabled inventory valuation "Automated" then this app will also cancel stock accounting entry. Product quantity, quants and accounting entries are managed properly.
    sitaram solutions developed new odoo app that will allow you to cancel/reset validated inventory adjustments
    cancel inventory adjustment
    reset inventory adjustment
    reset to draft inventory adjustment
    odoo inventory management
    manage product quantity
    manage stock move
    manage stock accounting entry
    cancel stock journal accounting entry
    delete stock move
    manage product quants
    manage stock quants
    odoo stock management
    reverse stock move
    reverse stock accounting entry
    reverse product stocks
""",
    "price": 10,
    "currency": "EUR",
    "author": "Sitaram",
    "depends": ["base", "stock", "account"],
    "data": ["views/inherited_inventory_adjustment.xml"],
    "website": "https://sitaramsolutions.in",
    "installable": True,
    "auto_install": False,
    "live_test_url": "https://youtu.be/UX4y2ddYgrQ",
    "images": ["static/description/banner.png"],
}
