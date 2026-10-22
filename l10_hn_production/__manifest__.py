{
    "name": "Honduras Producción",
    "summary": "Transferencias de materiales a bodega de producción con aprobación",
    "description": """
Al confirmar una orden de producción, genera una solicitud de transferencia interna
desde la Bodega A hacia la Bodega de Producción, descontando lo que ya existe en destino.
La transferencia requiere aprobación antes de crear el picking de inventario.
    """,
    "version": "19.0.1.0.21",
    "author": "Grupo Nahuiik",
    "website": "https://www.gruponahuiik.com",
    "license": "LGPL-3",
    "category": "Manufacturing",
    "depends": [
        "mrp",
        "stock",
        "stock_account",
        "l10n_hn_stock",
        "mail",
        "gts_branch_management",
    ],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "views/production_material_transfer_views.xml",
        "wizards/production_material_transfer_reject_wizard_views.xml",
        "views/mrp_production_views.xml",
        "views/mrp_production_overview_views.xml",
        "views/product_template_views.xml",
        "views/mrp_workcenter_views.xml",
        "views/res_company_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
}
