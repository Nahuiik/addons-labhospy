# -*- coding: utf-8 -*-
"""
Enlace de anticipo asociado a orden de venta.

Registra la asociación de un anticipo (pago) a una orden de venta,
para aplicarlo cuando se facture.
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleOrderAdvanceLink(models.Model):
    _name = 'sale.order.advance.link'
    _description = 'Abono/Anticipo Asociado a Orden de Venta'
    _order = 'create_date desc'
    _rec_name = 'display_name'
    _check_company_auto = True

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        required=True,
        ondelete='cascade',
        index=True,
    )
    payment_id = fields.Many2one(
        'account.payment',
        string='Abono/Anticipo',
        required=True,
        ondelete='cascade',
        index=True,
    )
    amount = fields.Monetary(
        string='Monto Asociado',
        required=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='sale_order_id.currency_id',
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='sale_order_id.company_id',
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        related='sale_order_id.partner_id',
        store=True,
        readonly=True,
    )
    display_name = fields.Char(
        string='Nombre',
        compute='_compute_display_name',
        store=True,
    )

    @api.depends('payment_id.name', 'amount', 'currency_id.symbol')
    def _compute_display_name(self):
        for rec in self:
            name = rec.payment_id.name or _('Abono/Anticipo')
            symbol = rec.currency_id.symbol or ''
            rec.display_name = f'{name} - {rec.amount:,.2f} {symbol}'

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('El monto asociado debe ser mayor que cero.'))

    @api.constrains('payment_id', 'sale_order_id')
    def _check_partner(self):
        for rec in self:
            if rec.payment_id.partner_id != rec.sale_order_id.partner_id:
                raise ValidationError(_(
                    'El Abono/Anticipo y la orden deben ser del mismo cliente.'
                ))

    @api.constrains('payment_id', 'amount')
    def _check_available_amount(self):
        for rec in self:
            if rec.amount > rec.payment_id.advance_available_amount:
                raise ValidationError(_(
                    'El monto (%s) excede el saldo disponible del Abono/Anticipo (%s).',
                    rec.amount, rec.payment_id.advance_available_amount
                ))
