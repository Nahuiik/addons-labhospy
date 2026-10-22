# -*- coding: utf-8 -*-
#############################################################################
#
#    Localization Honduras - AI Quotation Module
#
#    Copyright (C) 2024-TODAY
#    Author: Grupo Nahuiik
#
#############################################################################
from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    """
    Extends res.config.settings to add AI configuration.
    """
    _inherit = 'res.config.settings'
    
    # AI Provider Settings
    ai_provider = fields.Selection(
        [
            ('openai', 'OpenAI'),
            ('gemini', 'Google Gemini'),
            ('azure_openai', 'Azure OpenAI'),
            ('custom', 'Custom'),
        ],
        string='AI Provider',
        config_parameter='l10n_hn_ia.provider',
        default='openai',
        help='AI provider to use for quotation generation',
    )
    ai_api_key = fields.Char(
        string='API Key',
        config_parameter='l10n_hn_ia.api_key',
        help='API key for the AI provider',
    )
    ai_endpoint = fields.Char(
        string='Endpoint',
        config_parameter='l10n_hn_ia.endpoint',
        help='API endpoint URL (for custom providers or Azure OpenAI)',
    )
    ai_model = fields.Char(
        string='Model',
        config_parameter='l10n_hn_ia.model',
        help='AI model name (e.g., gpt-3.5-turbo, gemini-pro)',
    )
    ai_timeout = fields.Integer(
        string='Timeout (seconds)',
        config_parameter='l10n_hn_ia.timeout',
        default=30,
        help='Timeout for AI API calls in seconds',
    )
    ai_temperature = fields.Float(
        string='Temperature',
        config_parameter='l10n_hn_ia.temperature',
        default=0.7,
        help='Temperature for AI generation (0.0-1.0)',
    )
    ai_use_rag = fields.Boolean(
        string='Use RAG',
        config_parameter='l10n_hn_ia.use_rag',
        default=False,
        help='Use Retrieval Augmented Generation (RAG)',
    )
    
    # Quotation Settings
    ai_default_template_id = fields.Many2one(
        'sale.order.template',
        string='Default Quotation Template',
        config_parameter='l10n_hn_ia.default_template_id',
        help='Default quotation template to use',
    )
    ai_default_pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Default Price List',
        config_parameter='l10n_hn_ia.default_pricelist_id',
        help='Default price list to use',
    )
    ai_auto_create_without_review = fields.Boolean(
        string='Auto-create Quotation without Review',
        config_parameter='l10n_hn_ia.auto_create_without_review',
        default=False,
        help='Automatically create quotations without review (only for managers)',
        groups='l10n_hn_ia.ai_group_sales_manager',
    )
    ai_send_email_with_link = fields.Boolean(
        string='Send Email with Portal Link',
        config_parameter='l10n_hn_ia.send_email_with_link',
        default=False,
        help='Send email with portal link when creating quotation',
    )
    
    @api.model
    def get_values(self):
        """
        Get configuration values.
        """
        res = super(ResConfigSettings, self).get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        
        # Get default template and pricelist
        template_id = ICP.get_param('l10n_hn_ia.default_template_id', False)
        pricelist_id = ICP.get_param('l10n_hn_ia.default_pricelist_id', False)
        
        if template_id:
            res['ai_default_template_id'] = int(template_id)
        if pricelist_id:
            res['ai_default_pricelist_id'] = int(pricelist_id)
        
        return res
    
    def set_values(self):
        """
        Set configuration values.
        """
        super(ResConfigSettings, self).set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        
        # Set template and pricelist
        ICP.set_param('l10n_hn_ia.default_template_id', self.ai_default_template_id.id or '')
        ICP.set_param('l10n_hn_ia.default_pricelist_id', self.ai_default_pricelist_id.id or '')



