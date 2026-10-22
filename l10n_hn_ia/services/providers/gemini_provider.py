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
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    _logger.warning("Google Generative AI library not available. Install it with: pip install google-generativeai")


class GeminiProvider(AIProviderBase):
    """
    Google Gemini provider implementation.
    """
    
    def __init__(self, env):
        super().__init__(env)
        if not GEMINI_AVAILABLE:
            raise UserError(_("Google Generative AI library is not installed. Please install it with: pip install google-generativeai"))
        
        if not self.config.get('api_key'):
            raise UserError(_("Gemini API key is not configured. Please configure it in Settings."))
        
        genai.configure(api_key=self.config.get('api_key'))
    
    def suggest_quote(self, context):
        """
        Generate quotation suggestion using Google Gemini.
        
        Args:
            context (dict): Context data
            
        Returns:
            dict: Normalized response
        """
        try:
            prompt = self._prepare_prompt(context)
            model_name = self.config.get('model') or 'gemini-pro'
            temperature = self.config.get('temperature', 0.7)
            
            # Configure generation config
            generation_config = {
                "temperature": temperature,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
            
            # Get model
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config,
            )
            
            # Generate content
            response = model.generate_content(prompt)
            response_text = response.text
            
            parsed_response = self._parse_response(response_text)
            normalized_response = self._normalize_response(parsed_response)
            
            return normalized_response
            
        except Exception as e:
            _logger.error("Error calling Gemini API: %s", str(e))
            raise UserError(_("Error calling Gemini API: %s") % str(e))



