{
    "name": "Lock Price",
    "version": "18.2",
    "category": "Sales/Sales",
    "summary": "The Lock Price module enables managers to set fixed prices for products across sale orders, purchase orders, invoices, and account pricing, ensuring price consistency, preventing unauthorized modifications, price lock for users, fixed product pricing, Odoo price security, sale order price lock, purchase order price management, fixed pricing across transactions, account price control, invoicing price lock, Odoo sales price management, price modification prevention, product price consistency, Odoo pricing automation, purchase pricing control, Odoo price integrity, prevent price changes Odoo, sale price security, locked product prices, read-only pricing, sales order price control, purchase order price consistency, invoicing consistency, Odoo transaction price lock, locked price visibility, price accuracy, Odoo product pricing, price fixing in Odoo, purchase and sale price protection, product pricing consistency, invoice pricing security, sales invoice price lock, product price tracking, price management automation, pricing integrity across orders, control sale and purchase prices, prevent price tampering, Odoo pricing feature, lock price per product, Odoo locked price field, restrict price edits, automated price locking, price protection for invoices, locked price enforcement, fixed pricing management Odoo, and price stability for sales and purchase orders.",
    "description": "\n        The Lock Price module in Odoo enables managers to set fixed prices for products, preventing any changes to the price in sales orders, purchase orders, invoicing, and accounts. This ensures that product prices remain consistent across different stages of the sales and purchase cycle, providing greater control over pricing and preventing unauthorized adjustments.\n\n        Key Features:\n        1) Lock Price for Users:\n           - Managers can enable the \"Lock Sale, Purchase, Product, and Account Price\" Boolean option to lock the product prices for specific users, ensuring no modification.\n\n        2) Read-Only Price in Product View:\n           - When the price is locked, users can only view the locked price in the product view, making it impossible to edit.\n\n        3) Price Lock in Sale Orders, Purchase Orders, and Invoicing:\n           - Locked prices will appear as read-only in sales orders, purchase orders, credit notes, bills, and refunds, maintaining price integrity across transactions.\n\n        Use Cases:\n        - Ensure that product prices are consistent and prevent any unauthorized price changes.\n        - Control pricing during transactions across multiple Odoo modules.\n\n        Supported Views:\n        - Navigation to lock product prices:\n          * Product View: Sales \u2192 Products\n          * Sales Order View: Sales \u2192 Quotations\n          * Purchase Order View: Purchases \u2192 Requests for Quotation\n          * Invoicing View: Invoicing \u2192 Bills and Credit Notes\n    ",
    "author": "INKERP",
    "website": "https://www.inkerp.com/",
    "depends": [
        "sale_management",
        "account",
        "product",
        "purchase"
    ],
    "data": [
        "security/security.xml",
        "views/product_template_view.xml",
        "views/product_product_view.xml",
        "views/sale_order_view.xml",
        "views/account_move_view.xml",
        "views/purchase_order_view.xml"
    ],
    "images": [
        "static/description/banner.gif"
    ],
    "license": "OPL-1",
    "installable": True,
    "application": True,
    "auto_install": False,
    "price": "7.0",
    "currency": "EUR"
}