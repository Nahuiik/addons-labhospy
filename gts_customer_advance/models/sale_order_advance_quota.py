# -*- coding: utf-8 -*-
"""
Cuota del plan de pagos asociado a orden de venta.

Define las fechas y montos programados para el cobro.
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleOrderAdvanceQuota(models.Model):
    _name = 'sale.order.advance.quota'
    _description = 'Cuota de Plan de Pagos'
    _order = 'sequence, due_date'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(string='Secuencia', default=10)
    due_date = fields.Date(string='Fecha de Vencimiento', required=True)
    amount = fields.Monetary(
        string='Monto por cobrar',
        required=True,
        currency_field='currency_id',
    )
    amount_assigned = fields.Monetary(
        string='Monto asignado',
        currency_field='currency_id',
        default=0.0,
        help='Monto de Abono/Anticipo asignado a esta cuota.',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='sale_order_id.currency_id',
        store=True,
        readonly=True,
    )
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('paid', 'Pagado'),
    ], string='Estado', default='pending', readonly=True)
    payment_id = fields.Many2one(
        'account.payment',
        string='Pago Aplicado',
        readonly=True,
    )

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('El monto de la cuota debe ser mayor que cero.'))
