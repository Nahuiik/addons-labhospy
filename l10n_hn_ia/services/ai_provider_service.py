# -*- coding: utf-8 -*-
#############################################################################
#
#    Localization Honduras - AI Quotation Module
#
#    Copyright (C) 2024-TODAY
#    Author: Grupo Nahuiik
#
#############################################################################
import logging
from odoo import models, api, _
from odoo.exceptions import UserError
from .providers.openai_provider import OpenAIProvider
from .providers.gemini_provider import GeminiProvider
from .providers.azure_openai_provider import AzureOpenAIProvider

_logger = logging.getLogger(__name__)


class AIProviderService(models.AbstractModel):
    """
    Service to manage AI providers.
    """
    _name = 'ai.provider.service'
    _description = 'AI Provider Service'
    
    @api.model
    def get_provider(self):
        """
        Get the configured AI provider.
        
        Returns:
            AIProviderBase: Configured AI provider instance
        """
        ICP = self.env['ir.config_parameter'].sudo()
        provider = ICP.get_param('l10n_hn_ia.provider', 'openai')
        
        try:
            if provider == 'openai':
                return OpenAIProvider(self.env)
            elif provider == 'gemini':
                return GeminiProvider(self.env)
            elif provider == 'azure_openai':
                return AzureOpenAIProvider(self.env)
            else:
                raise UserError(_("Unknown AI provider: %s") % provider)
        except Exception as e:
            _logger.error("Error initializing AI provider: %s", str(e))
            raise UserError(_("Error initializing AI provider: %s") % str(e))
    
    @api.model
    def suggest_quote(self, context):
        """
        Generate quotation suggestion using the configured provider.
        
        Args:
            context (dict): Context data including lead information
            
        Returns:
            dict: Normalized response with quotation suggestion
        """
        provider = self.get_provider()
        return provider.suggest_quote(context)



