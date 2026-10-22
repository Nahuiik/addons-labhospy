# -*- coding: utf-8 -*-
"""
Extensión de sale.order para anticipos de clientes.

- Muestra anticipos disponibles del cliente (stat button, banner)
- Permite asociar anticipos a la orden (advance_link_ids)
- Plan de cuotas (advance_quota_ids)
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Anticipos asociados y plan de cuotas
    advance_link_ids = fields.One2many(
        'sale.order.advance.link',
        'sale_order_id',
        string='Anticipos Asociados',
    )
    advance_quota_ids = fields.One2many(
        'sale.order.advance.quota',
        'sale_order_id',
        string='Plan de Cuotas',
    )
    advance_linked_amount = fields.Monetary(
        string='Monto Anticipos Asociados',
        compute='_compute_advance_linked_amount',
        store=True,
        currency_field='currency_id',
    )
    advance_balance = fields.Monetary(
        string='Saldo pendiente',
        compute='_compute_advance_balance',
        currency_field='currency_id',
        help='Total de la cotización menos anticipos asignados',
    )
    advance_progress = fields.Float(
        string='Progreso Anticipos (%)',
        compute='_compute_advance_progress',
        help='Porcentaje del total cubierto por anticipos asociados',
    )
    advance_progress_display = fields.Char(
        string='Progreso',
        compute='_compute_advance_progress',
    )
    advance_calculation_display = fields.Char(
        string='Cálculo',
        compute='_compute_advance_progress',
        help='Texto del cálculo: porcentaje (anticipos / total)',
    )
    advance_show_generate_quotas_button = fields.Boolean(
        string='Mostrar Botón Generar Cuotas',
        compute='_compute_advance_show_generate_quotas',
    )

    has_available_advances = fields.Boolean(
        string='Tiene Anticipos Disponibles',
        compute='_compute_available_advances',
        help='Indica si el cliente tiene anticipos disponibles que se pueden aplicar'
    )
    available_advances_count = fields.Integer(
        string='Cantidad de Anticipos',
        compute='_compute_available_advances',
        help='Número de anticipos disponibles para este cliente'
    )
    available_advances_amount = fields.Monetary(
        string='Monto de Anticipos Disponibles',
        compute='_compute_available_advances',
        currency_field='currency_id',
        help='Monto total de anticipos disponibles para este cliente'
    )

    @api.depends('amount_total', 'advance_linked_amount', 'currency_id')
    def _compute_advance_balance(self):
        for order in self:
            order.advance_balance = (order.amount_total or 0) - (order.advance_linked_amount or 0)

    @api.depends('advance_link_ids.amount', 'advance_link_ids.currency_id')
    def _compute_advance_linked_amount(self):
        for order in self:
            if order.advance_link_ids:
                total = sum(
                    link.amount for link in order.advance_link_ids
                    if link.currency_id == order.currency_id
                )
                order.advance_linked_amount = total
            else:
                order.advance_linked_amount = 0.0

    @api.depends('advance_linked_amount', 'amount_total', 'currency_id')
    def _compute_advance_progress(self):
        for order in self:
            if order.amount_total and order.amount_total > 0:
                pct = min(100.0, (order.advance_linked_amount / order.amount_total) * 100)
                order.advance_progress = pct
                order.advance_progress_display = f'{pct:.1f}%'
                order.advance_calculation_display = (
                    f'{pct:.1f}% ({order.advance_linked_amount:.2f} / '
                    f'{order.amount_total:.1f} {order.currency_id.symbol or ""})'
                )
            else:
                order.advance_progress = 0.0
                order.advance_progress_display = '0%'
                order.advance_calculation_display = ''

    @api.depends('state', 'advance_quota_ids', 'amount_total')
    def _compute_advance_show_generate_quotas(self):
        for order in self:
            order.advance_show_generate_quotas_button = (
                order.state in ('draft', 'sent') and
                not order.advance_quota_ids and
                order.amount_total > 0
            )

    @api.depends('partner_id', 'company_id', 'currency_id', 'state')
    def _compute_available_advances(self):
        """
        Calcula los anticipos disponibles del cliente para esta orden de venta.
        Calcula para órdenes con partner (draft, sent, sale, done).
        """
        Payment = self.env['account.payment']

        for order in self:
            if (order.state in ('draft', 'sent', 'sale', 'done') and
                    order.partner_id and order.company_id):
                advances = Payment._get_available_advances_for_partner(
                    order.partner_id.id,
                    order.company_id.id,
                    order.currency_id.id,
                    partner_type='customer'
                )
                order.available_advances_count = len(advances)
                order.available_advances_amount = sum(
                    advances.mapped('advance_available_amount')
                )
                order.has_available_advances = order.available_advances_amount > 0
            else:
                order.has_available_advances = False
                order.available_advances_count = 0
                order.available_advances_amount = 0.0

    def action_view_available_advances(self):
        """
        Abre la vista de anticipos disponibles del cliente.

        Returns:
            dict: Acción para abrir la lista de anticipos disponibles
        """
        self.ensure_one()
        Payment = self.env['account.payment']
        advances = Payment._get_available_advances_for_partner(
            self.partner_id.id,
            self.company_id.id,
            self.currency_id.id,
            partner_type='customer'
        )
        return {
            'name': _('Anticipos Disponibles - %s', self.partner_id.name),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', advances.ids)],
            'context': {
                'create': False,
                'search_default_filter_advances_available': 1,
            },
        }

    def action_open_link_advance_wizard(self):
        """Abre el wizard para asociar anticipos a la orden (montos prellenados)."""
        self.ensure_one()
        return {
            'name': _('Asociar Anticipo'),
            'type': 'ir.actions.act_window',
            'res_model': 'link.advance.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
            },
        }

    def _distribute_advances_to_quotas(self, total_to_distribute, show_warning_if_excess=True):
        """
        Distribuye el monto total de anticipos a las cuotas del plan.
        Asigna secuencialmente: cada cuota recibe min(su monto, restante).
        Si el total excede la suma de cuotas, asigna el exceso a la última cuota y opcionalmente muestra advertencia.
        """
        self.ensure_one()
        quotas = self.advance_quota_ids.sorted(key=lambda q: (q.sequence, q.due_date))
        if not quotas:
            return
        total_quotas = sum(q.amount for q in quotas)
        remaining = total_to_distribute
        for i, quota in enumerate(quotas):
            if remaining <= 0:
                quota.amount_assigned = 0.0
                continue
            assign = min(quota.amount, remaining)
            quota.amount_assigned = assign
            remaining -= assign
        if remaining > 0:
            # Anticipo mayor que total de cuotas: asignar exceso a la última cuota
            last = quotas[-1]
            last.amount_assigned = last.amount_assigned + remaining
            if show_warning_if_excess:
                self.message_post(
                    body=_(
                        'Advertencia: El total de anticipos asociados (%s) es mayor que el total '
                        'del plan de cuotas (%s). El exceso se ha asignado a la última cuota.',
                        total_to_distribute, total_quotas
                    ),
                    message_type='notification',
                )

    def action_auto_link_advances(self):
        """Asocia automáticamente los anticipos disponibles hasta cubrir el total de la cotización
        y los distribuye en las cuotas del plan."""
        self.ensure_one()
        if not self.partner_id or not self.company_id or self.amount_total <= 0:
            return
        if not self.advance_quota_ids:
            raise UserError(_(
                'No hay plan de cuotas. Debe crear el plan de cuotas primero (botón "Generar cuotas") '
                'para poder asociar los anticipos automáticamente a las cuotas.'
            ))
        Payment = self.env['account.payment']
        advances = Payment._get_available_advances_for_partner(
            self.partner_id.id,
            self.company_id.id,
            self.currency_id.id,
            partner_type='customer'
        )
        linked_payment_ids = self.advance_link_ids.mapped('payment_id').ids
        advances = advances.filtered(lambda a: a.id not in linked_payment_ids)
        remaining = self.amount_total - self.advance_linked_amount
        if remaining <= 0:
            raise UserError(_('La cotización ya está cubierta por anticipos asociados.'))
        if not advances:
            raise UserError(_('No hay anticipos disponibles para este cliente o ya están asociados a esta orden.'))
        Link = self.env['sale.order.advance.link']
        total_linked = 0.0
        for adv in advances:
            if remaining <= 0:
                break
            amount = min(adv.advance_available_amount, remaining)
            if amount > 0:
                Link.create({
                    'sale_order_id': self.id,
                    'payment_id': adv.id,
                    'amount': amount,
                })
                total_linked += amount
                remaining -= amount
        if total_linked > 0:
            # Distribuir el total de anticipos asociados (incluye los recién creados)
            total = sum(
                link.amount for link in self.advance_link_ids
                if link.currency_id == self.currency_id
            )
            self._distribute_advances_to_quotas(total)
        return {'type': 'ir.actions.act_window_close'}

    def action_register_advance(self):
        """Abre el formulario para registrar un nuevo anticipo del cliente."""
        self.ensure_one()
        if not self.partner_id:
            from odoo.exceptions import UserError
            raise UserError(_('Debe seleccionar un cliente para registrar un anticipo.'))
        return {
            'name': _('Registrar Anticipo'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_amount': self.amount_total or 0,
                'default_currency_id': self.currency_id.id,
                'default_is_advance': True,
                'default_partner_type': 'customer',
                'default_payment_type': 'inbound',
                'default_sale_order_id': self.id,
            },
        }

    def action_generate_quotas(self):
        """Abre el wizard para generar el plan de cuotas con cantidad configurable."""
        self.ensure_one()
        if not self.partner_id or not self.amount_total:
            return
        return {
            'name': _('Generar Plan de Cuotas'),
            'type': 'ir.actions.act_window',
            'res_model': 'generate.quotas.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
            },
        }
