# -*- coding: utf-8 -*-
"""
Wizard para generar el plan de cuotas con cantidad configurable.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta


class GenerateQuotasWizard(models.TransientModel):
    _name = 'generate.quotas.wizard'
    _description = 'Generar Plan de Cuotas'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        required=True,
        readonly=True,
    )
    num_quotas = fields.Integer(
        string='Cantidad de cuotas',
        default=4,
        required=True,
        help='Número de cuotas mensuales a generar.',
    )
    amount_total = fields.Monetary(
        related='sale_order_id.amount_total',
        readonly=True,
    )
    currency_id = fields.Many2one(
        related='sale_order_id.currency_id',
        readonly=True,
    )
    amount_per_quota = fields.Monetary(
        string='Monto por cuota',
        compute='_compute_amount_per_quota',
        currency_field='currency_id',
        readonly=True,
    )

    @api.depends('sale_order_id.amount_total', 'num_quotas')
    def _compute_amount_per_quota(self):
        for wiz in self:
            if wiz.num_quotas and wiz.num_quotas > 0:
                wiz.amount_per_quota = (wiz.sale_order_id.amount_total or 0) / wiz.num_quotas
            else:
                wiz.amount_per_quota = 0.0

    @api.constrains('num_quotas')
    def _check_num_quotas(self):
        for wiz in self:
            if wiz.num_quotas < 1:
                raise ValidationError(_('La cantidad de cuotas debe ser al menos 1.'))
            if wiz.num_quotas > 60:
                raise ValidationError(_('La cantidad de cuotas no puede exceder 60.'))

    def action_confirm(self):
        """Genera el plan de cuotas según la cantidad indicada."""
        self.ensure_one()
        order = self.sale_order_id
        if not order.partner_id or not order.amount_total:
            raise UserError(_('La orden debe tener cliente y total para generar cuotas.'))
        if order.advance_quota_ids:
            raise UserError(_(
                'Ya existe un plan de cuotas. Elimine las cuotas actuales antes de generar uno nuevo.'
            ))
        if self.num_quotas < 1:
            raise UserError(_('La cantidad de cuotas debe ser al menos 1.'))
        base_date = order.date_order.date() if order.date_order else fields.Date.today()
        amount_per_quota = order.amount_total / self.num_quotas
        Quota = self.env['sale.order.advance.quota']
        for i in range(self.num_quotas):
            due_date = base_date + relativedelta(months=i + 1)
            Quota.create({
                'sale_order_id': order.id,
                'sequence': (i + 1) * 10,
                'due_date': due_date,
                'amount': amount_per_quota,
            })
        return {'type': 'ir.actions.act_window_close'}
