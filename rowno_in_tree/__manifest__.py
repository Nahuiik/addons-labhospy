{
    "name": "Row Number in Tree/List View",
    "version": "19.0.1.0.0",
    "summary": "Display row numbers in all tree/list views.",
    "category": "Other",
    "depends": ["web"],
    # Data / Views
    "data": [],
    # Assets to inject into backend
    "assets": {
        "web.assets_backend": [
            "rowno_in_tree/static/src/views/list/list_render.xml",
            "rowno_in_tree/static/src/js/list_renderer.esm.js",
            "rowno_in_tree/static/src/css/custom_styles.css",
        ],
    },
    # Module metadata
    "images": ["static/description/rowno_in_tree_list_dashboard.gif"],
    "license": "LGPL-3",
    "author": "Synodica Solutions Pvt. Ltd.",
    "website": "https://synodica.com",
    "maintainer": "Synodica Solutions Pvt. Ltd.",
    "support": "support@synodica.com",
    # Installation flags
    "installable": True,
    "application": True,
    "auto_install": False,
}
