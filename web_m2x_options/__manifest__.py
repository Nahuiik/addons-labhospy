# Copyright 2015 0k.io
# Copyright 2016 ACSONE SA/NV
# Copyright 2017 Tecnativa
# Copyright 2020 initOS GmbH.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "web_m2x_options",
    "version": "19.0.1.0.4",
    "category": "Web",
    "author": "initOS GmbH,"
    "ACSONE SA/NV, "
    "0k.io, "
    "Tecnativa, "
    "Sygel, "
    "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/web",
    "license": "AGPL-3",
    "depends": ["web", "base_setup"],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            (
                "after",
                "web/static/src/views/fields/standard_field_props.js",
                "web_m2x_options/static/src/views/fields/standard_field_props.esm.js",
            ),
            "web_m2x_options/static/src/components/form.esm.js",
            "web_m2x_options/static/src/components/base.xml",
        ]
    },
    "installable": True,
}
