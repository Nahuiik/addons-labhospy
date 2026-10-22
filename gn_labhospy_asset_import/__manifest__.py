{
    "name": "GN LabHosPy - Importacion de Activos Fijos",
    "summary": "Categorias, chatter y utilidades para importar el catalogo de activos fijos historico.",
    "version": "19.0.1.1.0",
    "depends": [
        "bi_account_asset",
        "l10n_hn_account",
        "gts_branch_management",
        "mail",
    ],
    "author": "Grupo Nahuiik",
    "website": "https://www.gruponahuiik.com",
    "license": "LGPL-3",
    "category": "Accounting",
    "description": """
Crea las 10 categorias de activos fijos utilizadas para la carga inicial
del catalogo historico de LABHOSPY sobre el modulo bi_account_asset.

- Mapea las cuentas del PCG existente (1020101-4 / 1020105 / 6020101).
- Usa diario Operaciones miscelaneas (MISCE).
- External IDs estables: gn_labhospy_asset_import.asset_cat_*.
""",
    "data": [
        "data/asset_categories.xml",
        "views/account_asset_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
