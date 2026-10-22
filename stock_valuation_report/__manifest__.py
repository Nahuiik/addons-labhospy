# -*- coding: utf-8 -*-
# Migrado a Odoo 19 - Basado en stock_valuation_on_date de TidyWay

{
    'name': 'Reporte de Valoración de Inventario por Fecha',
    'version': '19.0.1.1.0',
    'category': 'Inventory/Inventory',
    'summary': 'Reporte de valoración de stock en fecha específica (XLS/PDF)',
    'description': """
Reporte de Valoración de Inventario por Fecha
==============================================

Este módulo permite generar reportes de valoración de inventario 
en un rango de fechas específico.

Características:
- Filtrar por compañía, almacén, ubicación
- Filtrar por categorías de producto y por proveedor LabHosPy
- Exportar a PDF o Excel (XLSX)
- Ver resumen o detalle por producto
- Cálculo de inventario inicial, entradas, salidas, ajustes y final
""",
    'author': 'TidyWay (Migrado)',
    'website': 'https://tidyway.in',
    'depends': ['stock_account', 'gn_labhospy'],
    'data': [
        'security/stock_valuation_security.xml',
        'security/ir.model.access.csv',
        'wizard/stock_valuation_wizard_views.xml',
        'views/stock_valuation_report_template.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
