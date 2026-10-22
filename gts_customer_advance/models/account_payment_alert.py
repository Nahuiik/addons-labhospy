# -*- coding: utf-8 -*-
"""
Sistema de alertas para anticipos de clientes.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class AccountPaymentAlert(models.Model):
    """Modelo para alertas de anticipos"""
    _name = 'account.payment.alert'
    _description = 'Alerta de Anticipo'
    _order = 'date desc'

    payment_id = fields.Many2one(
        'account.payment',
        string='Anticipo',
        required=True,
        ondelete='cascade'
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        related='payment_id.partner_id',
        store=True
    )
    alert_type = fields.Selection([
        ('unapplied_30', 'Sin aplicar > 30 días'),
        ('unapplied_60', 'Sin aplicar > 60 días'),
        ('unapplied_90', 'Sin aplicar > 90 días'),
        ('low_balance', 'Saldo disponible bajo'),
    ], string='Tipo de Alerta', required=True)
    date = fields.Date(string='Fecha de Alerta', default=fields.Date.today)
    message = fields.Text(string='Mensaje')
    resolved = fields.Boolean(string='Resuelta', default=False)
    resolved_date = fields.Date(string='Fecha de Resolución')
    resolved_user_id = fields.Many2one('res.users', string='Resuelta por')

    def action_resolve(self):
        """Marca la alerta como resuelta"""
        self.ensure_one()
        self.write({
            'resolved': True,
            'resolved_date': fields.Date.today(),
            'resolved_user_id': self.env.user.id
        })

    @api.model
    def check_unapplied_advances(self):
        """Verifica anticipos sin aplicar y crea alertas"""
        today = fields.Date.today()
        date_30 = today - timedelta(days=30)
        date_60 = today - timedelta(days=60)
        date_90 = today - timedelta(days=90)
        
        # Buscar anticipos sin aplicar
        advances_30 = self.env['account.payment'].search([
            ('is_advance', '=', True),
            ('advance_applied_total', '=', 0),
            ('advance_available_amount', '>', 0),
            ('date', '<=', date_30),
            ('date', '>', date_60),
        ])
        
        advances_60 = self.env['account.payment'].search([
            ('is_advance', '=', True),
            ('advance_applied_total', '=', 0),
            ('advance_available_amount', '>', 0),
            ('date', '<=', date_60),
            ('date', '>', date_90),
        ])
        
        advances_90 = self.env['account.payment'].search([
            ('is_advance', '=', True),
            ('advance_applied_total', '=', 0),
            ('advance_available_amount', '>', 0),
            ('date', '<=', date_90),
        ])
        
        # Crear alertas
        for advance in advances_30:
            self._create_alert(advance, 'unapplied_30', 
                             _('Anticipo sin aplicar por más de 30 días'))
        
        for advance in advances_60:
            self._create_alert(advance, 'unapplied_60',
                             _('Anticipo sin aplicar por más de 60 días'))
        
        for advance in advances_90:
            self._create_alert(advance, 'unapplied_90',
                             _('Anticipo sin aplicar por más de 90 días'))

    def _create_alert(self, payment, alert_type, message):
        """Crea una alerta si no existe una activa"""
        existing = self.search([
            ('payment_id', '=', payment.id),
            ('alert_type', '=', alert_type),
            ('resolved', '=', False)
        ], limit=1)
        
        if not existing:
            self.create({
                'payment_id': payment.id,
                'alert_type': alert_type,
                'message': message,
            })
