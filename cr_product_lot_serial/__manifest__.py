# -*- coding: utf-8 -*-
# Part of Creyox Technologies
{
    'name': 'Display Lots/Serial Number of Product',
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    'category': 'Warehouse',
    'summary': """
    The Product Lots/Serial Number in Product Form Odoo app adds a dedicated 
    "Lots/Serial Number" page in the product form view. This feature lets users 
    easily view and manage all lots/serial numbers assigned to a specific product, 
    directly linked with the stock.lot module. Simplify product tracking, improve 
    inventory visibility, and streamline lot/serial number management in Odoo.
    Odoo product lots, 
    Odoo serial numbers, 
    Product form lots page, 
    Stock.lot integration, 
    Product tracking Odoo, 
    Inventory lots and serial numbers, 
    Odoo inventory management, 
    Lot/serial tracking, 
    Manage serial numbers in Odoo, 
    Product traceability Odoo,
    How can I view product lots and serial numbers directly in Odoo?
    Does this module show all assigned serial numbers for a product in Odoo?
    How is the stock.lot module connected with product lots in Odoo?
    Can I track product serial numbers from the product form view?
    How does the Lots/Serial Number tab improve product traceability in Odoo?
    Is it possible to manage lots and serials without going to stock operations in Odoo?
    How can I streamline inventory tracking using product lots in Odoo?
    Why is serial number tracking important for inventory management in Odoo?
    """,
    'license': 'LGPL-3',
    'version': '19.0.0.0',
    'description': """
    The Product Lots/Serial Number in Product Form Odoo app adds a dedicated 
    "Lots/Serial Number" page in the product form view. This feature lets users 
    easily view and manage all lots/serial numbers assigned to a specific product, 
    directly linked with the stock.lot module. Simplify product tracking, improve 
    inventory visibility, and streamline lot/serial number management in Odoo.
    Odoo product lots, 
    Odoo serial numbers, 
    Product form lots page, 
    Stock.lot integration, 
    Product tracking Odoo, 
    Inventory lots and serial numbers, 
    Odoo inventory management, 
    Lot/serial tracking, 
    Manage serial numbers in Odoo, 
    Product traceability Odoo,
    How can I view product lots and serial numbers directly in Odoo?
    Does this module show all assigned serial numbers for a product in Odoo?
    How is the stock.lot module connected with product lots in Odoo?
    Can I track product serial numbers from the product form view?
    How does the Lots/Serial Number tab improve product traceability in Odoo?
    Is it possible to manage lots and serials without going to stock operations in Odoo?
    How can I streamline inventory tracking using product lots in Odoo?
    Why is serial number tracking important for inventory management in Odoo?
""",
    'depends': ["base", "stock"],
    'data': [
        "security/ir.model.access.csv",
        "views/product_product_view.xml"
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    "images": ["static/description/banner.png", ],
    "price": 0,
    "currency": "USD"
}
