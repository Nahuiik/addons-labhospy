#
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013 Julius Network Solutions SARL <contact@julius.fr>
#    Copyright (C) 2015 credativ ltd. <info@credativ.co.uk>
#    Copyright (C) 2017-2020 Shurshilov Artem <shurshilov.a@yandex.ru>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#

{
    "name": "Product Tags",
    "version": "19.0.0.1",
    'license': 'OPL-1',
    "author": "Mario Matamoros",
    "website": "http://www.gruponahuiik.com",
    'summary': 'Product Tgas',
    'description': """Este modulo agregega etiquetas a los productos,
    permitiendo una mejor organización y filtrado de los productos en el sistema.
    Las etiquetas pueden ser jerárquicas, permitiendo una estructura de categorías
    y subcategorías para una mejor organización.""",
    "category": "Sales Management",
    "depends": [
        "product",
    ],
    "demo": [],
    "data": [
        "views/product_view.xml",
    ],
    "images": [
        "static/description/tags.png",
        "static/description/kanban.png",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
