# -*- coding: utf-8 -*-
{
    'name': "Invoice Landed Cost",

    'summary': "Add the invoice by landed cost line",

    'description': """
Landing costs are created from the list of invoices with the Supplier Invoices field,
in addition, for landing costs that do not have an invoice, the automatic exchange rate will be applied when doing so in Dollars.
A PDF report was created for the landing costs folder that contains the cost summary, details of Documents Entered into the Warehouse and the Detail of Import Expenses
    """,

    'author': 'Pragmatic S.A.C',
    'website': 'https://www.pragmatic.com.pe',
    'support': 'kmeza@pragmatic.com.pe',

    'category': 'Inventory/Operations',
    'version': '19.0.0.27',
    'license': 'AGPL-3',
    'currency': 'USD',
    'price': '15',

    'depends': ['stock', 'account', 'stock_landed_costs', 'purchase_stock'],

    'data': [
        'security/landed_cost_groups.xml',
        'security/ir.model.access.csv',
        'views/stock_landed_cost.xml',
        'views/landed_cost_sale_margin_wizard_views.xml',
        'report/landed_cost_report_templates.xml',
        'report/landed_cost_report.xml',
        'report/landed_cost_margin_report_templates.xml',
        'report/landed_cost_margin_report.xml',
    ],


    'images': ['static/description/icon.png']

}

