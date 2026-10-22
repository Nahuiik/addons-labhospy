# -*- coding: utf-8 -*-
{
    "name": "LABHOSPY Website",
    "summary": "Página principal y menú del sitio web LABHOSPY",
    "version": "19.0.1.0.9",
    "category": "Website/Website",
    "author": "LABHOSPY",
    "license": "LGPL-3",
    "depends": ["website"],
    "data": [
        "data/website_data.xml",
        "views/layout.xml",
        "views/header.xml",
        "views/menus.xml",
        "views/homepage.xml",
        "views/contactus.xml",
        "views/aboutus.xml",
        "views/footer.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "website_labhospy/static/src/scss/labhospy.scss",
        ],
    },
    "installable": True,
    "application": False,
}
