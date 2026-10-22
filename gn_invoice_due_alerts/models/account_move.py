# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    gn_days_to_due = fields.Integer(
        string='Dias para vencer',
        compute='_compute_gn_due_status',
        help='Dias entre hoy y la fecha de vencimiento. Negativo si ya '
             'esta vencida.')
    gn_due_status = fields.Selection(
        selection=[
            ('overdue', 'Vencida'),
            ('today', 'Vence hoy'),
            ('soon', 'Proxima a vencer'),
            ('upcoming', 'Futura'),
            ('none', 'Sin fecha / pagada'),
        ],
        string='Estado de vencimiento',
        compute='_compute_gn_due_status')

    @api.depends('invoice_date_due', 'payment_state', 'amount_residual',
                 'move_type', 'state')
    def _compute_gn_due_status(self):
        today = fields.Date.context_today(self)
        soon_days = self.env.company.due_alert_days_before or 3
        for move in self:
            due = move.invoice_date_due
            is_open = (
                move.move_type in ('in_invoice', 'in_refund')
                and move.state == 'posted'
                and move.payment_state in ('not_paid', 'partial')
                and move.amount_residual > 0
            )
            if not is_open or not due:
                move.gn_due_status = 'none'
                move.gn_days_to_due = 0
                continue
            delta = (due - today).days
            move.gn_days_to_due = delta
            if delta < 0:
                move.gn_due_status = 'overdue'
            elif delta == 0:
                move.gn_due_status = 'today'
            elif delta <= soon_days:
                move.gn_due_status = 'soon'
            else:
                move.gn_due_status = 'upcoming'
