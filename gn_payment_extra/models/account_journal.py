# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    is_credit_card = fields.Boolean(
        string='Tarjetas de Crédito',
        default=False,
        help='Marcar si este diario maneja pagos con tarjetas de crédito'
    )

    payment_mode = fields.Selection([
        ('efectivo', 'Efectivo'),
        ('tarjeta', 'Tarjeta'),
        ('transferencia', 'Transferencia'),
        ('none', 'No mostrar en cobros'),
    ], string='Tipo en Cobros de Cliente',
       help='Define en qué opción aparece este diario al registrar pagos de facturas de cliente. '
            'Si está vacío, se usa la lógica automática (Efectivo=cash, Tarjeta=banco+tarjetas, Transferencia=banco sin tarjetas). '
            '"No mostrar en cobros" excluye este diario del wizard de pago.')

