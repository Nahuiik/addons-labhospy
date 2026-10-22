# -*- coding: utf-8 -*-
{
    "name": "Stocks by Locations",
    "version": "19.0.1.0.0",
    "category": "Warehouse",
    "author": "faOtools",
    "website": "https://faotools.com/apps/19.0/stocks-by-locations-19-0-product-stock-balance-832",
    "license": "Other proprietary",
    "application": True,
    "installable": True,
    "auto_install": False,
    "depends": [
        "sale_stock"
    ],
    "data": [
        "security/security.xml",
        "data/data.xml",
        "security/ir.model.access.csv",
        "views/product_template.xml",
        "views/product_product.xml",
        "views/sale_order.xml",
        "views/res_config_settings.xml"
    ],
    "assets": {
        "web.assets_backend": [
                "product_stock_balance/static/src/components/location_hierarchy_container/*.js",
                "product_stock_balance/static/src/components/location_hierarchy_container/*.xml",
                "product_stock_balance/static/src/components/location_hierarchy_container/*.scss",
                "product_stock_balance/static/src/fields/locations_hierarchy/*.js",
                "product_stock_balance/static/src/fields/locations_hierarchy/*.xml",
                "product_stock_balance/static/src/fields/location_hierarchy_sale/*.js",
                "product_stock_balance/static/src/fields/location_hierarchy_sale/*.xml"
        ]
},
    "demo": [
        
    ],
    "external_dependencies": {},
    "summary": "The tool to make inventory data essential and comfortable for elaboration. Stocks analysis. Stock balance report. Inventory levels. Inventory report. Inventory chart. Stock hierarchy. Stock report. Qty by warehouse. Stocks by warehouses. Stock pivot. Quantity per locations. Stock move report. Products by warehouses. Warehouse levels. Warehouse report. Stock positioning. Product stocks by locations. Product stock on location. Stock position by location. Location on product. Product availability. Product inventory information. Stock Analysis Report. Product location. Product stocks report.  Manage product stocks",
    "description": """
For the full details look at static/description/index.html
* Features *
#odootools_proprietary""",
    "images": [
        "static/description/main.png"
    ],
    "price": "38.0",
    "currency": "EUR",
    "live_test_url": "https://faotools.com/my/tickets/newticket?&url_app_id=72&ticket_version=19.0&url_type_id=3",
}
