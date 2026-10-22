# -*- coding: utf-8 -*-
{
    'name': 'GN Varios',
    'version': '19.0.1.0.17',
    'summary': 'Modulo de soluciones varias Odoo 19 CE',
    'description': """
        Utilidades transversales para instancias Odoo 19 Community.

        Incluye validaciones de negocio adicionales según se vayan añadiendo
        (p. ej. facturas de proveedor en borrador).

        Productos: pestaña Garantía con maestro "Tiempo de Garantía".
        Inventario: columnas LabHosPy en listas de stock.quant (proveedor y código catálogo).
        Entregas (stock.picking): columnas opcionales Vendedor (pedido de venta) y Factura (cliente publicada).
        Facturas: un solo rótulo de diario en cabecera; «Referencia de pago» mostrada como «Notas» donde aplica.
        Con gts_branch_management: sucursal bajo el diario (columna derecha).
    """,
    'category': 'Tools',
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'product',
        'stock',
        'sale_stock',
        'gn_labhospy',
        'gts_branch_management',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/gn_warranty_time_views.xml',
        'views/account_move_views.xml',
        'views/product_template_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_quant_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
