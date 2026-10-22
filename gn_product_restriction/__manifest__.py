# -*- coding: utf-8 -*-
{
    'name': 'GN Restricción creación de productos',
    'version': '19.0.1.0.6',
    'category': 'Tools',
    'summary': 'Exige el grupo GN para crear plantillas y variantes de producto',
    'description': """
        Bloquea ``create()`` en ``product.template`` y ``product.product``
        para cualquier usuario que **no** pertenezca al grupo
        **«Permitir crear productos (GN)»**.

        Lectura, edición y borrado siguen gobernados por los permisos
        estándar de Odoo (ACLs de «Productos / Crear»).

        Incluye pruebas: ``--test-tags gn_product_restriction``.
    """,
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'depends': ['product', 'acs_hms_base', 'gn_replace_products'],
    'data': [
        'security/gn_product_restriction_groups.xml',
        'security/gn_product_restriction_access.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
    'license': 'OPL-1',
}
