# -*- coding: utf-8 -*-
{
    "name": "Distribución Analítica en Cabecera de Factura",
    "version": "19.0.1.3.0",
    "summary": "Analítica en facturas de proveedor: campo de cabecera que se "
               "propaga a las líneas y distribución por defecto según la "
               "sucursal del documento.",
    "description": """
Distribución analítica en cabecera de factura
=============================================

Agrega un campo de distribución analítica en la cabecera de las facturas
(cliente y proveedor). Al establecerlo, la analítica se aplica
automáticamente a todas las líneas de producto, evitando capturarla línea
por línea.

* Funciona en facturas de proveedor (in_invoice/in_refund) y de cliente
  (out_invoice/out_refund).
* Usa el widget nativo ``analytic_distribution`` (planes + porcentajes).
* Respeta la analítica capturada manualmente en una línea (no la sobrescribe
  al guardar; sí se vuelca a todas al editar el campo de cabecera).
""",
    "category": "Accounting/Accounting",
    "author": "LABHOSPY",
    "license": "LGPL-3",
    "depends": ["account", "analytic", "gts_branch_management"],
    "data": [
        "views/res_branch_views.xml",
        "views/account_move_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
