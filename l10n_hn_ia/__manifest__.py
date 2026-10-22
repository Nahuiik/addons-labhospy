# -*- coding: utf-8 -*-
#############################################################################
#
#    Localization Honduras - AI Quotation Module
#
#    Copyright (C) 2024-TODAY
#    Author: Grupo Nahuiik
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
{
    'name': 'Honduras Localization - AI Quotation Assistant',
    'version': '19.0.2.0.0',
    'summary': 'AI-powered quotation generation from leads with multi-cloud provider support',
    'description': """
        Honduras Localization - AI Quotation Assistant
        ===============================================
        This module integrates AI agents with Odoo 19 to assist and/or automate 
        quotation creation from leads (including Chatbot/Live Chat input), with 
        security controls, optional review, and audit logging.
        
        Features:
        * Multi-cloud AI provider abstraction (OpenAI, Gemini, Azure OpenAI, Custom)
        * Lead intention classification (quote, support, other)
        * Product/service suggestions with quantities, prices, and conditions
        * Automatic quotation draft creation from leads
        * Configurable quotation templates and price lists
        * Optional human review wizard before creation
        * Portal link sending to clients
        * Complete audit logging and traceability
        * Server actions and automation support
        * RAG (Retrieval Augmented Generation) support
    """,
    'category': 'Sales/Localization',
    'author': 'Grupo Nahuiik',
    'company': 'Grupo Nahuiik',
    'maintainer': 'Grupo Nahuiik',
    'website': 'http://gruponahuiik.com',
    'depends': [
        'base',
        'sale',
        'sale_management',
        'crm',
        'mail',
        'portal',
        'base_automation',
    ],
    'data': [
        'security/ai_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/ir_config_parameter.xml',
        'data/base_automation.xml',
        'views/ai_suggestion_log_views.xml',
        'views/crm_lead_views.xml',
        'views/sale_order_views.xml',
        'views/ai_config_settings_views.xml',
        'views/ai_menu_views.xml',
        'wizard/ai_quote_wizard_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'countries': ['hn'],
}

