# -*- coding: utf-8 -*-
{
    'name': 'Honduras - Municipios',
    'version': '2.0.0',
    'summary': 'Departamentos / Municipios para Honduras',
    'description': """
Este módulo añade los Municipios y Distritos de Honduras al módulo base_address_extended.
Oculta el campo de código postal (zip) cuando el país seleccionado es Honduras.
Útil para localización y gestión geográfica en Odoo.
""",
    'author': 'Grupo Nahuiik',
    'maintainer': 'Mario Matamoros',
    'website': 'https://gruponahuiik.com',
    'category': 'Localization',
    'license': 'OPL-1',
    'support': 'info@gruponahuiik.com',
    'depends': ['base', 'base_address_extended', 'contacts'],
    'data': [
        'data/res_state_data.xml',
        'data/res_city_data.xml',
        'data/res_country_data.xml',
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': False,
}
