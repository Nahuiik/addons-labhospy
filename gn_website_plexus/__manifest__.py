# -*- coding: utf-8 -*-
{
    "name": "GN Website Plexus",
    "summary": "Animación tipo plexus como snippet para el sitio web.",
    "version": "1.0.0",
    "category": "Website/Website",
    "author": "GN",
    "website": "https://www.gn.com",
    "maintainer": "GN",
    "license": "LGPL-3",
    "depends": ["website"],
    "data": [
        "views/snippets.xml",
        "views/website_pages.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "gn_website_plexus/static/src/scss/animation.scss",
            "gn_website_plexus/static/src/js/animation.js",
        ],
        "website.assets_editor": [
            "gn_website_plexus/static/src/scss/animation.scss",
            "gn_website_plexus/static/src/js/animation.js",
            "gn_website_plexus/static/src/js/animation_editor.js",
        ],
    },
    "installable": True,
    "application": False,
}
