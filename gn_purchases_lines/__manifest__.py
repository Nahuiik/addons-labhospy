# -*- coding: utf-8 -*-
{
    'name': "GN Import Purchase Order Lines",
    'summary': """Importar líneas de orden de compra desde CSV/Excel""",
    'description': """
        Permite importar líneas de orden de compra masivamente desde archivos CSV o Excel.
        Características:
        - Importación masiva de líneas de compra
        - Soporte para CSV y Excel
        - Opciones para tomar detalles del producto o del archivo
        - Importación por código, código de barras o nombre
        - Validación de datos antes de importar
    """,
    'author': "Grupo Nahuiik",
    'website': "http://odoo.gruponahuiik.com",
    'category': 'Purchase',
    'version': '19.0.1.0.1',
    'license': 'LGPL-3',
    'depends': [
        'purchase',
        'base_import',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/purchase_order_views.xml',
        'wizard/import_purchase_lines_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

