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
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CrmLead(models.Model):
    """
    Extends crm.lead to add AI-powered quotation generation.
    """
    _inherit = 'crm.lead'
    
    x_intent = fields.Selection(
        [
            ('none', 'None'),
            ('quote', 'Quote'),
            ('support', 'Support'),
            ('other', 'Other'),
        ],
        string='AI Intent',
        default='none',
        help='AI-classified intention of the lead',
    )
    x_ai_payload = fields.Json(
        string='AI Payload',
        help='AI-generated payload with quotation suggestions',
    )
    x_ready_for_quote = fields.Boolean(
        string='Ready for Quote',
        default=False,
        help='Indicates if the lead is ready for quotation generation',
    )
    x_sale_order_id = fields.Many2one(
        'sale.order',
        string='Generated Sale Order',
        help='Sale order generated from this lead',
        copy=False,
    )
    x_ai_last_log_id = fields.Many2one(
        'ai.suggestion.log',
        string='Last AI Log',
        help='Last AI suggestion log for this lead',
        copy=False,
    )
    x_ai_suggestion_count = fields.Integer(
        string='AI Suggestions',
        compute='_compute_ai_suggestion_count',
    )
    
    def _compute_ai_suggestion_count(self):
        """
        Compute the number of AI suggestions for this lead.
        """
        for lead in self:
            lead.x_ai_suggestion_count = self.env['ai.suggestion.log'].search_count([
                ('lead_id', '=', lead.id)
            ])
    
    def action_ai_suggest_quote(self):
        """
        Action to generate AI suggestion for quotation.
        """
        self.ensure_one()
        
        try:
            # Prepare context
            context = self._prepare_ai_context()
            
            # Get AI provider service
            ai_service = self.env['ai.provider.service']
            provider = ai_service.get_provider()
            
            # Prepare prompt (we need to call it through the provider)
            prompt = provider._prepare_prompt(context)
            
            # Generate suggestion
            response = provider.suggest_quote(context)
            
            # Create log
            log = self.env['ai.suggestion.log'].create({
                'lead_id': self.id,
                'provider': self.env['ir.config_parameter'].sudo().get_param('l10n_hn_ia.provider', 'openai'),
                'model_name': self.env['ir.config_parameter'].sudo().get_param('l10n_hn_ia.model', ''),
                'prompt': prompt,
                'response_raw': json.dumps(response, indent=2),
                'parsed_payload': response,
                'state': 'suggested' if response.get('intent') == 'quote' else 'draft',
                'user_id': self.env.user.id,
            })
            
            # Update lead
            self.write({
                'x_intent': response.get('intent', 'none'),
                'x_ai_payload': response,
                'x_ready_for_quote': response.get('intent') == 'quote',
                'x_ai_last_log_id': log.id,
            })
            
            # If intent is quote and auto-create is enabled, open wizard
            ICP = self.env['ir.config_parameter'].sudo()
            auto_create = ICP.get_param('l10n_hn_ia.auto_create_without_review', 'False') == 'True'
            
            if response.get('intent') == 'quote':
                if auto_create and self.env.user.has_group('l10n_hn_ia.ai_group_sales_manager'):
                    # Auto-create quotation
                    return self.action_ai_create_quote()
                else:
                    # Open wizard for review
                    return self.action_ai_review_quote_wizard()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('AI Suggestion'),
                    'message': _('AI suggestion generated. Intent: %s') % response.get('intent', 'none'),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error("Error generating AI suggestion: %s", str(e))
            raise UserError(_("Error generating AI suggestion: %s") % str(e))
    
    def _prepare_ai_context(self):
        """
        Prepare context for AI provider.
        
        Returns:
            dict: Context data
        """
        self.ensure_one()
        
        context = {
            'name': self.name,
            'description': self.description,
            'partner_name': self.partner_id.name if self.partner_id else '',
            'email_from': self.email_from,
            'phone': self.phone,
            'source_id': {
                'id': self.source_id.id,
                'name': self.source_id.name,
            } if self.source_id else None,
            'type': self.type,
            'stage_id': {
                'id': self.stage_id.id,
                'name': self.stage_id.name,
            } if self.stage_id else None,
        }
        
        return context
    
    def action_ai_review_quote_wizard(self):
        """
        Action to open the review quote wizard.
        """
        self.ensure_one()
        
        if not self.x_ai_payload or self.x_intent != 'quote':
            raise UserError(_("No AI suggestion available for this lead."))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Review AI Quotation'),
            'res_model': 'ai.quote.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lead_id': self.id,
                'default_partner_id': self.partner_id.id if self.partner_id else False,
            },
        }
    
    def action_ai_create_quote(self):
        """
        Action to create quotation from AI suggestion.
        This is called directly or from the wizard.
        """
        self.ensure_one()
        
        if not self.x_ai_payload or self.x_intent != 'quote':
            raise UserError(_("No AI suggestion available for this lead."))
        
        # This will be called from the wizard
        # For now, just return the wizard action
        return self.action_ai_review_quote_wizard()
    
    def action_view_ai_suggestions(self):
        """
        Action to view AI suggestions for this lead.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('AI Suggestions'),
            'res_model': 'ai.suggestion.log',
            'view_mode': 'tree,form',
            'domain': [('lead_id', '=', self.id)],
            'context': {'default_lead_id': self.id},
            'target': 'current',
        }
    
    def action_view_generated_quote(self):
        """
        Action to view the generated quotation.
        """
        self.ensure_one()
        if not self.x_sale_order_id:
            raise UserError(_("No quotation has been generated for this lead."))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Quotation'),
            'res_model': 'sale.order',
            'res_id': self.x_sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

