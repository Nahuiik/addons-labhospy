# -*- coding: utf-8 -*-
{
    'name': 'Wizard Inventario (LabHosPy)',
    'version': '19.0.1.0.2',
    'category': 'Inventory/Inventory',
    'summary': 'Wizard OWL de inventario físico con filtros LabHosPy, impresión PDF/Excel y ajustes',
    'description': """
        Pantalla OWL de inventario físico basada en stock.quant:

        - Filtros: Almacén, Ubicación, Proveedor (LabHosPy), Modelo y Código de Catálogo.
        - Opción de mostrar u ocultar cantidades a la mano (conteo ciego).
        - Impresión en PDF y Excel (hoja de conteo).
        - Captura de cantidades contadas en pantalla y aplicación del
          ajuste de inventario (inventory_quantity + action_apply_inventory).
    """,
    'author': 'Grupo Nahuiik / Realeza',
    'license': 'LGPL-3',
    'depends': [
        'stock',
        'gn_labhospy',
        'gn_varios',
        'report_xlsx',
    ],
    'data': [
        'security/ir.model.access.csv',
        'reports/report_actions.xml',
        'reports/inventory_adjustment_template.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'assets': {
        'web.assets_backend': [
            'gn_inventory_ajustment/static/src/inventory_adjustment/**/*.js',
            'gn_inventory_ajustment/static/src/inventory_adjustment/**/*.xml',
            'gn_inventory_ajustment/static/src/inventory_adjustment/**/*.scss',
        ],
    },
}
