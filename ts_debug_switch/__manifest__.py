# -*- coding: utf-8 -*-
#############################################################################
#
#    Techvaria Solutions Pvt. Ltd.
#
#    Copyright (C) 2025-Techvaria Solutions(<https://techvaria.com>)
#    Author: Techvaria Solutions Pvt. Ltd.(info@techvaria.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################

{
    'name': 'Quick Debug Switch',
    'version': '2.0.0',
    'category': 'Productivity',
    'summary': 'Easily toggle Odoo Debug Mode (Developer Mode) with a single click from any screen.',
    'description': """
        Quick Debug Switch is a lightweight Odoo utility that lets users instantly
        toggle Debug Mode without navigating through settings or changing URLs.
        Ideal for developers and functional consultants who frequently access technical features.
    """,
    'author': 'Techvaria',
    'company': 'Techvaria',
    'maintainer': 'Techvaria',
    'website': 'https://techvaria.com',
    'depends': ['web'],
    'data': [
        'security/security.xml',
    ],
    'assets': {
        'web.assets_backend': ['ts_debug_switch/static/src/core/**/*'],
    },
    'images': [
        'static/description/screen.jpg',
    ],
    'license': 'OPL-1',
    'installable': True,
    'auto_install': False,
}
