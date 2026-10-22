# -*- coding: utf-8 -*-
{
    'name': 'GN Transformación Paquete → Unidad',
    'version': '19.0.1.0.1',
    'category': 'Inventory/Inventory',
    'summary': 'Desempaqueta un producto A en producto B conservando el costo total',
    'description': """
Transformación de empaque
=========================

Permite convertir un producto empaque (ej. pack de 15 unidades) en su producto
unidad destino, transfiriendo el valor de inventario íntegro al producto resultante.

Basado en la lógica de transformación de empaque de COFARMA, adaptado para DGLOBAL.
    """,
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'license': 'LGPL-3',
    'depends': [
        'product',
        'stock',
        'stock_account',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/pack_transform_views.xml',
        'views/product_template_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
