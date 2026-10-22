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
from odoo import models, _
from odoo.exceptions import UserError
from ..ai_provider_base import AIProviderBase

_logger = logging.getLogger(__name__)

try:
    import openai
    AZURE_OPENAI_AVAILABLE = True
except ImportError:
    AZURE_OPENAI_AVAILABLE = False
    _logger.warning("OpenAI library not available. Install it with: pip install openai")


class AzureOpenAIProvider(AIProviderBase):
    """
    Azure OpenAI provider implementation.
    """
    
    def __init__(self, env):
        super().__init__(env)
        if not AZURE_OPENAI_AVAILABLE:
            raise UserError(_("OpenAI library is not installed. Please install it with: pip install openai"))
        
        if not self.config.get('api_key'):
            raise UserError(_("Azure OpenAI API key is not configured. Please configure it in Settings."))
        
        if not self.config.get('endpoint'):
            raise UserError(_("Azure OpenAI endpoint is not configured. Please configure it in Settings."))
        
        # Configure Azure OpenAI
        openai.api_type = "azure"
        openai.api_key = self.config.get('api_key')
        openai.api_base = self.config.get('endpoint')
        openai.api_version = "2023-05-15"  # Default version, can be configured
    
    def suggest_quote(self, context):
        """
        Generate quotation suggestion using Azure OpenAI.
        
        Args:
            context (dict): Context data
            
        Returns:
            dict: Normalized response
        """
        try:
            prompt = self._prepare_prompt(context)
            model = self.config.get('model') or 'gpt-35-turbo'
            temperature = self.config.get('temperature', 0.7)
            
            # Call Azure OpenAI API
            response = openai.ChatCompletion.create(
                engine=model,  # Azure uses 'engine' instead of 'model'
                messages=[
                    {"role": "system", "content": "Eres un asistente experto en análisis de leads y generación de cotizaciones comerciales. Siempre responde en formato JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                timeout=self.config.get('timeout', 30),
            )
            
            response_text = response.choices[0].message.content
            parsed_response = self._parse_response(response_text)
            normalized_response = self._normalize_response(parsed_response)
            
            return normalized_response
            
        except Exception as e:
            _logger.error("Error calling Azure OpenAI API: %s", str(e))
            raise UserError(_("Error calling Azure OpenAI API: %s") % str(e))



