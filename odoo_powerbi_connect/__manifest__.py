# -*- coding: utf-8 -*-
##########################################################################
# Author      : Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# Copyright(c): 2015-Present Webkul Software Pvt. Ltd.
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://store.webkul.com/license.html/>
##########################################################################

{
    'name': 'Odoo Power BI Connector',
    'version': '4.2.2',
    'category': 'Generic Modules',
    'author': 'Webkul Software Pvt. Ltd.',
    'website': 'https://store.webkul.com/odoo-powerbi-connector.html',
    'live_test_url': 'https://odoodemo.webkul.com/?module=odoo_powerbi_connect',
    'sequence': 1,
    'license': "Other proprietary",
    'summary': 'Power BI Connector',
    'description': """

Odoo Power BI Connector
=======================

This module allows you to integrate your Poweri BI with Odoo and then you can start synchronizing data between Odoo and Power BI.
--------------------------------------------------------------------------


Some of the salient features of the connector are:-
--------------------------------------------

    1. Import/Export Workspaces

    2. Export newly created datasets.

    3. Export/Update/Delete any model's data in tables.

    4. Import power BI reports and view on odoo.

    5. Import power BI dashboards and view on odoo.

    6. Create dynamic server actions for any model.

    7. Configure cron to auto sync data for any model.

This module works very well with latest version of Odoo 14.0
------------------------------------------------------------------------------
    """,
    'depends': [
        'base','mail'
    ],
    'data': [
        'security/powerbi_connector_security.xml',
        'security/powerbi_model_records.xml',
        'security/ir.model.access.csv',

        'data/powerbi_sequence.xml',
        'data/powerbi_server_actions.xml',
	    'data/powerbi_cron.xml',

        'wizard/powerbi_message_wizard_view.xml',
        'wizard/table_column_wizard_view.xml',
        'wizard/powerbi_wizard_view.xml',
        'wizard/powerbi_credentials_wizard_view.xml',
        'wizard/unpublish_message_wizard_view.xml',
        'wizard/powerbi_table_wizard_view.xml',
        'wizard/powerbi_table_column_export_wizard_view.xml',
        'wizard/powerbi_table_column_import_wizard_view.xml',

        'views/res_config_settings_view.xml',
        'views/powerbi_connection_view.xml',
        'views/powerbi_dataset_view.xml',
        'views/powerbi_table_view.xml',
        'views/powerbi_workspace_view.xml',
        'views/powerbi_dashboards_view.xml',
        'views/powerbi_reports_view.xml',
        'views/powerbi_connector_dashboard.xml',
        'views/powerbi_connector_dashboard_accessibility.xml',
        'views/powerbi_template.xml',
        'views/powerbi_menus.xml',
        'views/powerbi_sync_log_views.xml',

        'data/demo/powerbi_demo_data.xml',
    ],

    'external_dependencies': {'python' : ['msal']},
    'images': ['static/description/banner.gif'],
    'application': True,
    'installable': True,
    'auto_install': False,
    'price': 399,
    'currency': 'USD',
    'pre_init_hook': 'pre_init_check',
}
