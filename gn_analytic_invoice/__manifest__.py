{
    "name": "Distribución Analítica en Facturas de Proveedor",
    "version": "19.0.1.2.0",
    "category": "Accounting",
    "summary": "Plantillas de factura de proveedor con distribución analítica; "
               "sin reparto analítico automático en ventas ni en facturas de cliente",
    "author": "GNCS",
    "website": "https://gncs.io",
    "license": "LGPL-3",
    "depends": ["account", "analytic", "purchase", "sale"],
    "data": [
        "security/ir.model.access.csv",
        "views/analytic_distribution_template_views.xml",
        "views/vendor_invoice_template_views.xml",
        "views/account_journal_views.xml",
        "views/account_move_views.xml",
    ],
    "installable": True,
    "application": False,
}
