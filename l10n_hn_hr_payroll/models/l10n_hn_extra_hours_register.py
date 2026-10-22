# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import fields, models


class L10nHnExtraHoursRegister(models.Model):
    """Registro de Horas Extra aplicadas desde Planilla"""
    _name = 'l10n.hn.extra.hours.register'
    _description = 'Registro Horas Extra'

    version_id = fields.Many2one('hr.version', string='Contrato', required=True, ondelete='cascade')
    payroll_sheet_id = fields.Many2one('l10n.hn.payroll.sheet', string='Planilla', required=True, ondelete='cascade')
    he_25 = fields.Float(string='HE 25%', digits=(10, 2), default=0)
    he_50 = fields.Float(string='HE 50%', digits=(10, 2), default=0)
    he_75 = fields.Float(string='HE 75%', digits=(10, 2), default=0)
    he_100 = fields.Float(string='HE 100%', digits=(10, 2), default=0)
    amount_25 = fields.Float(string='Monto 25%', digits=(12, 2), default=0)
    amount_50 = fields.Float(string='Monto 50%', digits=(12, 2), default=0)
    amount_75 = fields.Float(string='Monto 75%', digits=(12, 2), default=0)
    amount_100 = fields.Float(string='Monto 100%', digits=(12, 2), default=0)
