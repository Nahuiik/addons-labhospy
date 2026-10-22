# -*- coding: utf-8 -*-
{
    'name': 'Honduras — Libros legales (Diario, Mayor, Inventarios y Balances)',
    'version': '19.0.1.0.8',
    'category': 'Accounting/Localizations',
    'author': 'Labhospy',
    'summary': 'Libro Diario, Libro Mayor y Libro de Inventarios y Balances (XLSX y QWeb).',
    'description': (
        'Informes de apoyo para el cumplimiento de libros contables de uso mercantil habitual en Honduras: '
        'asientos cronológicos (Diario), movimientos y saldos por cuenta (Mayor), y situación de saldos / '
        'inventarios (Inventarios y Balances). Validar formato y requisitos de autorización con su contador y la municipalidad.'
    ),
    'depends': ['account', 'l10n_hn_reports'],
    'external_dependencies': {
        'python': ['xlsxwriter'],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/hn_legal_books_menus_views.xml',
        'report/hn_legal_books_report.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
