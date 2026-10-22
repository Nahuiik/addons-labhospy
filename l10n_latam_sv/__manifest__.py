# -*- coding: utf-8 -*-
{
    'name': 'Honduras - Document Types',
    'version': '2.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Document types for Honduras',
    'description': """
        This module extends l10n_latam_base to add specific document types for El Salvador:
        - DNI (Documento Único de Identidad)
        - RTN (Número de Identificación Tributaria)
        - Pasaporte
        - Carnet de Residente
        - Otro documento
    """,
    'author': 'miliky',
    'maintainer': 'José Emilio flores Meléndez',
    'website': 'https://github.com/miliky/odoo18',
    'category': 'Localization',
    'license': 'LGPL-3',
    'images': ['static/description/banner.jpg'],
    'support': 'jefm@outlook.com',
    'price': 0.0,
    'currency': 'USD',
    'depends': ['l10n_latam_base'],
    'data': [
        'data/l10n_latam_identification_type_data.xml',
        'data/res.partner.industry.csv',
        'views/res_company_view.xml',
        'views/res_partner_views.xml',
        'views/res_partner_industry_views.xml',
    ],
    'installable': True,
    'application': False,
}