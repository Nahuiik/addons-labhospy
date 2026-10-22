# -*- coding: utf-8 -*-
{
    "name": "Sucursal y Analítica en Tesorería",
    "version": "19.0.1.0.0",
    "summary": "Muestra la sucursal en documentos de tesorería (débito/crédito) "
               "y propaga su distribución analítica a las líneas y al asiento "
               "contable.",
    "description": """
Sucursal y analítica en tesorería
=================================

* Muestra el campo **Sucursal** en el formulario de débito/crédito.
* Cada sucursal puede configurar una **distribución analítica de tesorería**.
* Al elegir la sucursal o al guardar el documento, esa analítica se vuelca a
  las líneas que no tengan analítica propia (no sobrescribe lo capturado a mano).
* Como el asiento contable se genera copiando la analítica de cada línea,
  esta se **hereda automáticamente** en los apuntes del asiento.
""",
    "category": "Accounting",
    "author": "Grupo Nahuiik",
    "website": "https://www.gruponahuiik.com",
    "license": "OPL-1",
    "depends": [
        "gn_banks",
        "gn_banks_dashboard",
        "gts_branch_management",
        "analytic",
    ],
    "data": [
        "views/res_branch_views.xml",
        "views/debit_credit_views.xml",
    ],
    "installable": True,
    "application": False,
}
