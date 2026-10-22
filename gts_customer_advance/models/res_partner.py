# -*- coding: utf-8 -*-
"""
Extensión de res.partner para mostrar anticipos del cliente.
"""

from odoo import models, fields, api, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    advance_payment_ids = fields.One2many(
        'account.payment',
        'partner_id',
        string='Anticipos de Cliente',
        domain=[('is_advance', '=', True), ('partner_type', '=', 'customer')]
    )
    vendor_advance_payment_ids = fields.One2many(
        'account.payment',
        'partner_id',
        string='Anticipos de Proveedor',
        domain=[('is_advance', '=', True), ('partner_type', '=', 'supplier')]
    )
    
    total_advances_available = fields.Monetary(
        string='Total Anticipos Disponibles',
        compute='_compute_advances_summary',
        currency_field='currency_id',
        help='Total de anticipos disponibles para aplicar a facturas'
    )
    
    total_advances_applied = fields.Monetary(
        string='Total Anticipos Aplicados',
        compute='_compute_advances_summary',
        currency_field='currency_id',
        help='Total de anticipos ya aplicados a facturas'
    )
    
    total_advances_received = fields.Monetary(
        string='Total Anticipos Recibidos',
        compute='_compute_advances_summary',
        currency_field='currency_id',
        help='Total de anticipos recibidos del cliente'
    )
    
    advances_count = fields.Integer(
        string='Cantidad de Anticipos',
        compute='_compute_advances_summary',
        help='Número total de anticipos del cliente'
    )

    # Campos para anticipos de proveedores
    vendor_advances_count = fields.Integer(
        string='Cantidad de Anticipos de Proveedor',
        compute='_compute_vendor_advances_summary',
        help='Número total de anticipos de proveedor'
    )
    total_vendor_advances_available = fields.Monetary(
        string='Total Anticipos de Proveedor Disponibles',
        compute='_compute_vendor_advances_summary',
        currency_field='currency_id',
        help='Total de anticipos de proveedor disponibles para aplicar a facturas'
    )
    total_vendor_advances_applied = fields.Monetary(
        string='Total Anticipos de Proveedor Aplicados',
        compute='_compute_vendor_advances_summary',
        currency_field='currency_id',
        help='Total de anticipos de proveedor ya aplicados a facturas'
    )
    total_vendor_advances_paid = fields.Monetary(
        string='Total Anticipos de Proveedor Pagados',
        compute='_compute_vendor_advances_summary',
        currency_field='currency_id',
        help='Total de anticipos pagados al proveedor'
    )
    
    @api.depends('advance_payment_ids', 'advance_payment_ids.amount', 
                 'advance_payment_ids.advance_available_amount', 
                 'advance_payment_ids.advance_applied_total')
    def _compute_advances_summary(self):
        """Calcula resumen de anticipos del cliente."""
        for partner in self:
            advances = partner.advance_payment_ids.filtered(
                lambda p: p.state in ('in_process', 'paid', 'draft')
            )
            
            partner.advances_count = len(advances)
            partner.total_advances_received = sum(advances.mapped('amount'))
            partner.total_advances_applied = sum(advances.mapped('advance_applied_total'))
            partner.total_advances_available = sum(advances.mapped('advance_available_amount'))
            
            # Si no hay anticipos, inicializar en 0
            if not advances:
                partner.advances_count = 0
                partner.total_advances_received = 0.0
                partner.total_advances_applied = 0.0
                partner.total_advances_available = 0.0
    
    @api.depends('vendor_advance_payment_ids', 'vendor_advance_payment_ids.amount', 
                 'vendor_advance_payment_ids.advance_available_amount', 
                 'vendor_advance_payment_ids.advance_applied_total')
    def _compute_vendor_advances_summary(self):
        """Calcula resumen de anticipos de proveedor."""
        for partner in self:
            advances = partner.vendor_advance_payment_ids.filtered(
                lambda p: p.state in ('in_process', 'paid', 'draft')
            )
            
            partner.vendor_advances_count = len(advances)
            partner.total_vendor_advances_paid = sum(advances.mapped('amount'))
            partner.total_vendor_advances_applied = sum(advances.mapped('advance_applied_total'))
            partner.total_vendor_advances_available = sum(advances.mapped('advance_available_amount'))
            
            # Si no hay anticipos, inicializar en 0
            if not advances:
                partner.vendor_advances_count = 0
                partner.total_vendor_advances_paid = 0.0
                partner.total_vendor_advances_applied = 0.0
                partner.total_vendor_advances_available = 0.0
