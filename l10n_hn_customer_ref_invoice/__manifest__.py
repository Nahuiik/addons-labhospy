{
    'name': 'Validación factura cliente por referencia SAR',
    'version': '19.0.1.0.4',
    'category': 'Accounting/Localizations',
    'summary': 'Publica facturas de cliente usando la referencia del cliente como número fiscal',
    'description': """
        Permite validar facturas de cliente en borrador tomando el número fiscal
        desde el campo «Referencia del cliente» (ref), con formato SAR
        000-002-01-00022827 (19 caracteres).

        No modifica el botón «Confirmar» estándar: solo actúa la acción dedicada
        «Validar con referencia SAR» y la acción masiva en lista.
    """,
    'author': 'Grupo Nahuiik',
    'website': 'https://www.gruponahuiik.com',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'l10n_hn_account',
        'gn_labhospy',
    ],
    'data': [
        'security/groups.xml',
        'views/account_move_views.xml',
        'data/ir_actions_server.xml',
    ],
    'installable': True,
    'application': False,
}
