{
    "name": "Lots and Serials in Invoice Lines",
    "summary": "Show Lots and Serials in invoice lines and the invoice PDF report.",
    "description": """
        Track lots/serial numbers from the sale order to the delivery and show them on invoice lines as well as on the printed invoice.
    """,
    "author": "Mohamed Yaseen Dahab",
    "website": "https://www.speedy-world.com",
    "category": "Accounting",
    "version": "19.0.1.0.0",
    "depends": ["account", "sale", "stock"],
    "data": [
        "security/ir.model.access.csv",
        "views/sale_order.xml",
        "views/purchase_order.xml",
        "views/stock_lot_tree.xml",
        "views/account_move.xml",
        "views/account_report.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
