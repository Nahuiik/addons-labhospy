################################################################################
#
#    Odoo Sphere Solutions.
#
#    Copyright (C) 2023-TODAY Odoo Sphere Solutions.
#
#    You can modify it under the terms of the Odoo Proprietary License v1.0,
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    Odoo Proprietary License v1.0 for more details.
#
#    You should have received a copy of the Odoo Proprietary License v1.0 along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#####################################################################################
{
    'name': "Customer Statements | Customer Overdue Payments | Vendor Bank Statements",
    'version': '19.0.1.0.3',
    'summary': """1. The app allows you to view detailed accounting statements for both customers and vendors.
                  2. It provides information about overdue invoices and payment details, helping you track outstanding payments.
                  3. You can send statements of account reports to your customers and vendors via email directly from the app.
                  4. The app enables you to print overdue statement reports for customers and suppliers.
                  5. The app displays the total due amount and total overdue amount for customers and vendors. Total due represents the remaining amount owed, and total overdue represents the amount that has exceeded the payment term selected on invoices.""",
    'description': """1. The app allows you to view detailed accounting statements for both customers and vendors.
                  2. It provides information about overdue invoices and payment details, helping you track outstanding payments.
                  3. You can send statements of account reports to your customers and vendors via email directly from the app.
                  4. The app enables you to print overdue statement reports for customers and suppliers.
                  5. The app displays the total due amount and total overdue amount for customers and vendors. Total due represents the remaining amount owed, and total overdue represents the amount that has exceeded the payment term selected on invoices.""",
    'author': "Odoo Sphere Solutions",
    'company': 'Odoo Sphere Solutions',
    'maintainer': 'Odoo Sphere Solutions',
    'category': 'Extra Tools',
    'depends': ['base', 'account', 'contacts', 'mail', 'web', 'payment'],
    'data': [
        'security/ir.model.access.csv',
        'data/email_templates.xml',
        'data/ir_cron.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        'reports/print_reports.xml',
        'reports/report_templates.xml',
        'wizards/custom_customer_statements_wizard_view.xml',
    ],
    'demo': [],
    'qweb': [],
    'installable': True,
    'auto_install': False,
    'application': False,
    'assets': {},
    'images': ['static/description/banner.gif'],
    'license': 'OPL-1',
    'currency': 'USD',
    'price': 54.98,
}
