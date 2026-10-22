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


class AISuggestionLog(models.Model):
    """
    Model for AI suggestion logs (audit trail).
    """
    _name = 'ai.suggestion.log'
    _description = 'AI Suggestion Log'
    _order = 'date desc'
    _rec_name = 'name'
    
    name = fields.Char(
        string='Name',
        required=True,
        default=lambda self: _('New'),
        copy=False,
    )
    lead_id = fields.Many2one(
        'crm.lead',
        string='Lead',
        ondelete='cascade',
        index=True,
    )
    sale_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        ondelete='set null',
        index=True,
    )
    provider = fields.Selection(
        [
            ('openai', 'OpenAI'),
            ('gemini', 'Google Gemini'),
            ('azure_openai', 'Azure OpenAI'),
            ('custom', 'Custom'),
        ],
        string='Provider',
        required=True,
    )
    model_name = fields.Char(
        string='Model Name',
        help='AI model used for this suggestion',
    )
    prompt = fields.Text(
        string='Prompt',
        help='Prompt sent to the AI provider',
    )
    response_raw = fields.Text(
        string='Raw Response',
        help='Raw response from the AI provider',
    )
    parsed_payload = fields.Json(
        string='Parsed Payload',
        help='Parsed response payload in JSON format',
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('suggested', 'Suggested'),
            ('applied', 'Applied'),
            ('failed', 'Failed'),
        ],
        string='State',
        default='draft',
        required=True,
    )
    error_msg = fields.Text(
        string='Error Message',
        help='Error message if the suggestion failed',
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user,
        required=True,
    )
    date = fields.Datetime(
        string='Date',
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )
    
    @api.model
    def create(self, vals):
        """
        Override create to generate sequence.
        """
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('ai.suggestion.log') or _('New')
        return super(AISuggestionLog, self).create(vals)
    
    def action_view_lead(self):
        """
        Action to view the lead.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lead'),
            'res_model': 'crm.lead',
            'res_id': self.lead_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_sale_order(self):
        """
        Action to view the sale order.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale Order'),
            'res_model': 'sale.order',
            'res_id': self.sale_id.id,
            'view_mode': 'form',
            'target': 'current',
        }



