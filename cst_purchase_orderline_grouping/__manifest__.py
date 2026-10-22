# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": " Purchase Order Line Grouping ",
    'summary': """Easily organize and display your Purchase Order Line grouped by product categories.""",
    "description": """
        This Module improves the way purchase order lines are displayed in RFQ and purchase orders. 
        Instead of showing all products in a flat list, it automatically groups them by their Product Categories, 
        allowing users to view, manage, and print organized order lines for better clarity.
    """,
    "author": "CodeSphere Tech",
    "website": "https://www.codespheretech.in/",
    "category": 'Purchase',
    "version": "19.0.1.0.1",
    'sequence': 0,
    "currency": "USD",
    "price": "0",
    "depends": ['purchase',],
    "data": [],
    'images': ['static/description/Banner.png'],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}
