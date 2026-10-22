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
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AIQuoteWizardLine(models.TransientModel):
    """
    Wizard line for quotation lines.
    """
    _name = 'ai.quote.wizard.line'
    _description = 'AI Quote Wizard Line'
    
    wizard_id = fields.Many2one(
        'ai.quote.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
    )
    name = fields.Text(
        string='Description',
        required=True,
    )
    product_uom_qty = fields.Float(
        string='Quantity',
        required=True,
        default=1.0,
    )
    price_unit = fields.Float(
        string='Unit Price',
        required=True,
    )
    discount = fields.Float(
        string='Discount (%)',
        default=0.0,
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        required=True,
    )
    note = fields.Text(
        string='Note',
        help='Note about this product',
    )


class AIQuoteWizard(models.TransientModel):
    """
    Wizard for reviewing and creating quotations from AI suggestions.
    """
    _name = 'ai.quote.wizard'
    _description = 'AI Quote Wizard'
    
    lead_id = fields.Many2one(
        'crm.lead',
        string='Lead',
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
    )
    template_id = fields.Many2one(
        'sale.order.template',
        string='Quotation Template',
        help='Template to use for the quotation',
    )
    pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Price List',
        required=True,
        help='Price list to use for the quotation',
    )
    validity_days = fields.Integer(
        string='Validity (days)',
        default=15,
        help='Validity period in days',
    )
    line_ids = fields.One2many(
        'ai.quote.wizard.line',
        'wizard_id',
        string='Quotation Lines',
    )
    note = fields.Text(
        string='Terms and Conditions',
        help='Terms and conditions for the quotation',
    )
    send_portal_link = fields.Boolean(
        string='Send Portal Link',
        default=True,
        help='Send portal link to the customer',
    )
    
    @api.model
    def default_get(self, fields_list):
        """
        Set default values from AI payload.
        """
        res = super(AIQuoteWizard, self).default_get(fields_list)
        
        lead_id = self.env.context.get('default_lead_id')
        if not lead_id:
            return res
        
        lead = self.env['crm.lead'].browse(lead_id)
        if not lead or not lead.x_ai_payload:
            return res
        
        # Set defaults from lead
        res['lead_id'] = lead.id
        res['partner_id'] = lead.partner_id.id if lead.partner_id else False
        
        # Get defaults from config
        ICP = self.env['ir.config_parameter'].sudo()
        template_id = ICP.get_param('l10n_hn_ia.default_template_id', False)
        pricelist_id = ICP.get_param('l10n_hn_ia.default_pricelist_id', False)
        
        if template_id:
            res['template_id'] = int(template_id)
        if pricelist_id:
            res['pricelist_id'] = int(pricelist_id)
        elif lead.partner_id and lead.partner_id.property_product_pricelist:
            res['pricelist_id'] = lead.partner_id.property_product_pricelist.id
        
        # Get payload
        payload = lead.x_ai_payload
        res['validity_days'] = payload.get('validity_days', 15)
        res['note'] = payload.get('terms', '')
        
        # Create lines from payload
        lines = []
        for line_data in payload.get('lines', []):
            product = self._find_product(line_data)
            if not product:
                # Skip if product not found
                continue
            
            line_vals = {
                'product_id': product.id,
                'name': line_data.get('note', product.name),
                'product_uom_qty': line_data.get('qty', 1.0),
                'price_unit': line_data.get('price', product.list_price),
                'discount': line_data.get('discount', 0.0),
                'product_uom_id': product.uom_id.id,
                'note': line_data.get('note', ''),
            }
            lines.append((0, 0, line_vals))
        
        res['line_ids'] = lines
        
        return res
    
    def _find_product(self, line_data):
        """
        Find product by default_code or name.
        
        Args:
            line_data (dict): Line data from AI payload
            
        Returns:
            product.product: Product found or False
        """
        Product = self.env['product.product']
        
        # Try to find by default_code
        if line_data.get('default_code'):
            product = Product.search([
                ('default_code', '=', line_data.get('default_code'))
            ], limit=1)
            if product:
                return product
        
        # Try to find by name
        if line_data.get('name'):
            product = Product.search([
                ('name', '=ilike', line_data.get('name'))
            ], limit=1)
            if product:
                return product
        
        return False
    
    def action_create_quotation(self):
        """
        Create quotation from wizard data.
        """
        self.ensure_one()
        
        if not self.line_ids:
            raise UserError(_("Please add at least one product to the quotation."))
        
        # Prepare quotation values
        quote_vals = {
            'partner_id': self.partner_id.id,
            'pricelist_id': self.pricelist_id.id,
            'x_generated_by_ai': True,
            'x_lead_id': self.lead_id.id,
            'x_ai_log_id': self.lead_id.x_ai_last_log_id.id if self.lead_id.x_ai_last_log_id else False,
            'note': self.note,
            'validity_date': (fields.Date.today() + timedelta(days=self.validity_days)) if self.validity_days else False,
        }
        
        # Create quotation
        quotation = self.env['sale.order'].create(quote_vals)
        
        # Create lines
        for line in self.line_ids:
            line_vals = {
                'order_id': quotation.id,
                'product_id': line.product_id.id,
                'name': line.name or line.product_id.name,
                'product_uom_qty': line.product_uom_qty,
                'product_uom': line.product_uom_id.id,
                'price_unit': line.price_unit,
            }
            if line.discount:
                line_vals['discount'] = line.discount
            self.env['sale.order.line'].create(line_vals)
        
        # Apply template if specified (after creating lines to avoid override)
        if self.template_id:
            quotation.sale_order_template_id = self.template_id.id
            # Only apply template if no lines exist (template will add its own lines)
            if not quotation.order_line:
                quotation.onchange_sale_order_template_id()
        
        # Recalculate prices
        quotation._recompute_prices()
        
        # Update log state
        if self.lead_id.x_ai_last_log_id:
            self.lead_id.x_ai_last_log_id.write({
                'state': 'applied',
                'sale_id': quotation.id,
            })
        
        # Update lead
        self.lead_id.write({
            'x_sale_order_id': quotation.id,
        })
        
        # Send portal link if requested
        if self.send_portal_link:
            self._send_portal_link(quotation)
        
        # Return action to view quotation
        return {
            'type': 'ir.actions.act_window',
            'name': _('Quotation'),
            'res_model': 'sale.order',
            'res_id': quotation.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def _send_portal_link(self, quotation):
        """
        Send portal link to customer.
        
        Args:
            quotation: sale.order record
        """
        try:
            # Post message on lead
            if self.lead_id:
                try:
                    # Try to get portal URL
                    if hasattr(quotation, 'get_portal_url'):
                        portal_url = quotation.get_portal_url()
                    else:
                        # Fallback: construct portal URL manually
                        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                        portal_url = f"{base_url}/my/quotes/{quotation.id}"
                except Exception as e:
                    _logger.warning("Error getting portal URL: %s", str(e))
                    base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                    portal_url = f"{base_url}/my/quotes/{quotation.id}"
                
                message = _(
                    "Quotation %s has been generated. "
                    "Portal link: <a href='%s'>%s</a>"
                ) % (quotation.name, portal_url, portal_url)
                self.lead_id.message_post(body=message)
            
            # Send email if configured
            ICP = self.env['ir.config_parameter'].sudo()
            send_email = ICP.get_param('l10n_hn_ia.send_email_with_link', 'False') == 'True'
            
            if send_email and quotation.partner_id.email:
                # Create mail template or use default
                template = self.env.ref('l10n_hn_ia.email_template_quotation_portal', raise_if_not_found=False)
                if template:
                    template.send_mail(quotation.id, force_send=True)
                else:
                    # Send simple email
                    quotation.message_post_with_view(
                        'mail.message_user_assigned',
                        subject=_('Quotation %s') % quotation.name,
                        email_values={'email_to': quotation.partner_id.email},
                    )
        except Exception as e:
            _logger.error("Error sending portal link: %s", str(e))
            # Don't raise error, just log it

