{
    'name': 'GN LabHosPy',
    'summary': 'Agrega características de proveedor/catalogo y control de productos',
    'version': '1.0.62',
    'depends': [
        'gn_permissions',
        'gts_branch_management',
        'purchase',
        'purchase_stock',
        'product',
        'professional_templates',
        'sale',
        'sale_stock',
        'stock',
        'product_expiry',
        'account',
        'report_xlsx',
    ],
    'category': 'Tools',
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'license': 'LGPL-3',
    'description': """
Agrega características en los productos de proveedor y catálogo, lleva control de productos controlados.
- Campos de proveedor y catálogo en productos.
- Campo booleano para indicar si es un producto controlado.
- Maestro de proveedores de laboratorio accesible desde Configuración.
- Informe «Venta de sustancias químicas controladas» y validaciones en facturas/recepciones.
    """,
    'data': [
        'security/ir.model.access.csv',
        'views/labhospy_application_use_views.xml',
        'views/labhospy_supplier_view.xml',
        'views/res_branch_views.xml',
        'views/product_template_views.xml',
        'views/res_config_settings_views.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'views/account_move_views.xml',
        'views/stock_picking_type_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_move_line_operation_views.xml',
        'views/product_product_stock_report_views.xml',
        'report/gn_labhospy_controlled_substances_report_templates.xml',
        'report/gn_labhospy_controlled_substances_report.xml',
        'views/controlled_substances_client_action_views.xml',
        'views/controlled_substances_report_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'gn_labhospy/static/src/js/controlled_substances_report_action.js',
            'gn_labhospy/static/src/xml/controlled_substances_report_action.xml',
            'gn_labhospy/static/src/js/sale_order_line_controlled_highlight.js',
            'gn_labhospy/static/src/js/stock_report_search_panel.js',
            'gn_labhospy/static/src/xml/stock_report_search_panel.xml',
            'gn_labhospy/static/src/js/stock_at_date_export.js',
            'gn_labhospy/static/src/xml/stock_at_date_export.xml',
        ],
    },
    'installable': True,
    'application': False,
}
