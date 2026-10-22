{
    'name': 'Costos en destino por picking (importación)',
    'summary': (
        'Divide la recepción de una compra internacional en dos pickings y '
        'permite gastos adicionales (permisos, aranceles, impuesto por '
        'producción) que solo afectan a los productos del picking indicado.'
    ),
    'version': '19.0.1.0.1',
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'license': 'LGPL-3',
    'category': 'Inventory/Purchase',
    'depends': [
        'stock',
        'purchase_stock',
        'stock_landed_costs',
        'invoice_in_landed_cost',
        'gn_labhospy',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/import_landed_cost_products.xml',
        'wizard/purchase_split_reception_wizard_views.xml',
        'views/stock_landed_cost_views.xml',
        'views/stock_picking_views.xml',
        'views/purchase_order_views.xml',
        'report/landed_cost_report_templates.xml',
    ],
    'installable': True,
    'application': False,
}
