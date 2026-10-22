# -*- coding: utf-8 -*-
# Part of Creyox Technologies
{
    'name': 'Stock Picking/Move From invoice',
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    'category': 'Warehouse',
    'summary': """
    Enhance your inventory and accounting workflow with this Odoo module 
    that allows creating stock pickings or stock moves directly from invoices 
    and vendor bills. Automate stock operations, reduce manual entries, and 
    ensure accurate synchronization between accounting and inventory management.
    Odoo stock picking from invoice
    Odoo stock moves from vendor bill
    Odoo invoice to stock picking automation,
    Odoo vendor bill stock integration,
    Odoo inventory and accounting synchronization,
    Odoo stock management automation,
    Odoo create stock moves from invoice,
    Odoo vendor bill to inventory workflow,
    Odoo stock and invoice integration module,
    Odoo accounting and inventory automation,
    How to create stock pickings directly from invoices in Odoo?
    Can I generate stock moves from vendor bills in Odoo?
    What is the best way to link vendor bills with stock pickings in Odoo?
    How does Odoo automate inventory from invoices?
    Which Odoo module helps create stock moves from vendor bills?
    How to synchronize inventory and accounting workflows in Odoo?
    Can stock picking be automated from invoices in Odoo?
    How to reduce manual work between vendor bills and stock operations in Odoo?
    What are the benefits of creating stock moves from invoices in Odoo?
    How to set up automatic stock pickings for vendor bills in Odoo?
    """,
    'version': '19.0.0.0',
    'license': 'LGPL-3',
    'description': """
    Enhance your inventory and accounting workflow with this Odoo module 
    that allows creating stock pickings or stock moves directly from invoices 
    and vendor bills. Automate stock operations, reduce manual entries, and 
    ensure accurate synchronization between accounting and inventory management.
    Odoo stock picking from invoice
    Odoo stock moves from vendor bill
    Odoo invoice to stock picking automation,
    Odoo vendor bill stock integration,
    Odoo inventory and accounting synchronization,
    Odoo stock management automation,
    Odoo create stock moves from invoice,
    Odoo vendor bill to inventory workflow,
    Odoo stock and invoice integration module,
    Odoo accounting and inventory automation,
    How to create stock pickings directly from invoices in Odoo?
    Can I generate stock moves from vendor bills in Odoo?
    What is the best way to link vendor bills with stock pickings in Odoo?
    How does Odoo automate inventory from invoices?
    Which Odoo module helps create stock moves from vendor bills?
    How to synchronize inventory and accounting workflows in Odoo?
    Can stock picking be automated from invoices in Odoo?
    How to reduce manual work between vendor bills and stock operations in Odoo?
    What are the benefits of creating stock moves from invoices in Odoo?
    How to set up automatic stock pickings for vendor bills in Odoo?
     """,
    'depends': ['base', 'account', 'sale_stock', 'sale', 'stock'],
    'data': [
        'views/config_parameter_view.xml',
        'views/account_move_inherit_view.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    "images": ["static/description/banner.png"],
    "price": 0,
    "currency": "USD"
}
