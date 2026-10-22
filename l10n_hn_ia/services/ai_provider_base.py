# -*- coding: utf-8 -*-
#############################################################################
#
#    Localization Honduras - AI Quotation Module
#
#    Copyright (C) 2024-TODAY
#    Author: Grupo Nahuiik
#
#############################################################################
import json
import logging
from abc import ABC, abstractmethod
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AIProviderBase(ABC):
    """
    Base class for AI providers.
    All AI providers must extend this class and implement the abstract methods.
    """
    
    def __init__(self, env):
        """
        Initialize the AI provider.
        
        Args:
            env: Odoo environment
        """
        self.env = env
        self.config = self._get_config()
    
    def _get_config(self):
        """
        Get configuration from ir.config_parameter.
        
        Returns:
            dict: Configuration dictionary
        """
        ICP = self.env['ir.config_parameter'].sudo()
        return {
            'api_key': ICP.get_param('l10n_hn_ia.api_key', ''),
            'endpoint': ICP.get_param('l10n_hn_ia.endpoint', ''),
            'model': ICP.get_param('l10n_hn_ia.model', ''),
            'timeout': int(ICP.get_param('l10n_hn_ia.timeout', '30')),
            'temperature': float(ICP.get_param('l10n_hn_ia.temperature', '0.7')),
            'use_rag': ICP.get_param('l10n_hn_ia.use_rag', 'False') == 'True',
        }
    
    @abstractmethod
    def suggest_quote(self, context):
        """
        Generate quotation suggestion from context.
        
        Args:
            context (dict): Context data including lead information
            
        Returns:
            dict: Normalized response with structure:
                {
                    "intent": "quote",
                    "customer": {"name": "...", "email": "..."},
                    "lines": [
                        {"default_code": "SaaS-STD", "qty": 10, "price": 25.0, 
                         "discount": 0, "note": "..."},
                        {"name": "Soporte anual", "qty": 1, "price": 1200.0}
                    ],
                    "validity_days": 15,
                    "terms": "Pago 50% anticipo, 50% a entrega"
                }
        """
        pass
    
    def _prepare_prompt(self, context):
        """
        Prepare the prompt for the AI provider.
        
        Args:
            context (dict): Context data
            
        Returns:
            str: Formatted prompt
        """
        lead_description = context.get('description', '')
        lead_name = context.get('name', '')
        partner_name = context.get('partner_name', '')
        email = context.get('email_from', '')
        phone = context.get('phone', '')
        source = context.get('source_id', {}).get('name', '') if context.get('source_id') else ''
        
        # Get RAG context if enabled
        rag_text = ''
        if self.config.get('use_rag'):
            rag_context = self._get_rag_context(context)
            if rag_context:
                rag_text = f"\nContexto adicional:\n{rag_context}\n"
        
        prompt = f"""Analiza el siguiente lead y genera una sugerencia de cotización en formato JSON.

Información del Lead:
- Nombre: {lead_name}
- Descripción: {lead_description}
- Cliente: {partner_name}
- Email: {email}
- Teléfono: {phone}
- Fuente: {source}
{rag_text}

Instrucciones:
1. Clasifica la intención: "quote", "support", o "other"
2. Si la intención es "quote", genera una sugerencia de cotización con:
   - Productos/servicios sugeridos (usar default_code si está disponible, o name)
   - Cantidades estimadas
   - Precios sugeridos
   - Descuentos aplicables
   - Términos y condiciones
   - Días de validez (por defecto 15)

3. Si la intención no es "quote", devuelve solo la intención clasificada.

Respuesta esperada en formato JSON:
{{
    "intent": "quote",
    "customer": {{
        "name": "Nombre del cliente",
        "email": "email@example.com"
    }},
    "lines": [
        {{
            "default_code": "PROD-001",
            "qty": 1,
            "price": 100.0,
            "discount": 0,
            "note": "Nota sobre el producto"
        }},
        {{
            "name": "Nombre del producto",
            "qty": 1,
            "price": 50.0
        }}
    ],
    "validity_days": 15,
    "terms": "Términos y condiciones de la cotización"
}}

Si la intención no es "quote":
{{
    "intent": "support",
    "customer": {{
        "name": "Nombre del cliente",
        "email": "email@example.com"
    }}
}}
"""
        return prompt
    
    def _get_rag_context(self, context):
        """
        Get RAG context from attachments or knowledge articles.
        
        Args:
            context (dict): Context data
            
        Returns:
            str: RAG context
        """
        # TODO: Implement RAG retrieval from ir.attachment or knowledge.article
        # This is a placeholder for future implementation
        return ""
    
    def _parse_response(self, response_text):
        """
        Parse the response from the AI provider.
        
        Args:
            response_text (str): Raw response text
            
        Returns:
            dict: Parsed response
        """
        try:
            # Try to extract JSON from the response
            # Some providers may return markdown or other formats
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)
            
            parsed = json.loads(response_text)
            return parsed
        except json.JSONDecodeError as e:
            _logger.error("Error parsing AI response: %s", str(e))
            raise UserError(_("Error parsing AI response: %s") % str(e))
    
    def _normalize_response(self, parsed_response):
        """
        Normalize the response to ensure it has the expected structure.
        
        Args:
            parsed_response (dict): Parsed response
            
        Returns:
            dict: Normalized response
        """
        normalized = {
            'intent': parsed_response.get('intent', 'other'),
            'customer': parsed_response.get('customer', {}),
            'lines': parsed_response.get('lines', []),
            'validity_days': parsed_response.get('validity_days', 15),
            'terms': parsed_response.get('terms', ''),
        }
        
        return normalized

