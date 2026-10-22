# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import date
from calendar import monthrange


class L10nHnPayrollCutoffConfig(models.Model):
    """Configuración de fechas de corte para planilla (HE del 21 mes ant - 20 mes actual = 2da quincena)"""
    _name = 'l10n.hn.payroll.cutoff.config'
    _description = 'Payroll Cutoff Config'
    _order = 'year desc, period_number'

    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                  default=lambda self: self.env.company)
    year = fields.Integer(string='Año', required=True, default=lambda self: fields.Date.today().year)
    period_number = fields.Selection([
        ('1', 'Primera Quincena (1-15)'),
        ('2', 'Segunda Quincena (16-Último)'),
    ], string='Quincena', required=True)
    cutoff_start_day = fields.Integer(string='Día Inicio Corte', required=True, default=6,
                                      help='Día del mes donde inicia el período de corte (ej. 6 para 1ra quincena)')
    cutoff_end_day = fields.Integer(string='Día Fin Corte', required=True, default=5,
                                    help='Día del mes donde termina el período de corte (ej. 5 para 1ra quincena)')
    cutoff_from_previous_month = fields.Boolean(string='Inicio en Mes Anterior', default=True,
                                                help='Si True, cutoff_start_day aplica al mes anterior')

    @api.constrains('cutoff_start_day', 'cutoff_end_day')
    def _check_days(self):
        for rec in self:
            if rec.cutoff_start_day < 1 or rec.cutoff_start_day > 31:
                raise ValidationError(_('Día inicio debe estar entre 1 y 31.'))
            if rec.cutoff_end_day < 1 or rec.cutoff_end_day > 31:
                raise ValidationError(_('Día fin debe estar entre 1 y 31.'))

    @api.model
    def get_cutoff_dates(self, payroll_period):
        """
        Devuelve (date_from, date_to) para el rango de HE a incluir en esta planilla.
        Usa primero los parámetros globales (Configuración > Nómina), luego el modelo
        l10n.hn.payroll.cutoff.config como fallback.
        Ejemplo 2da quincena feb-2026: 21 ene - 20 feb
        """
        if not payroll_period or not payroll_period.date_start:
            return None, None
        period_number = payroll_period.period_number
        year = payroll_period.year
        month = payroll_period.month
        # Prioridad 1: Parámetros globales (res.config.settings)
        ICP = self.env['ir.config_parameter'].sudo()
        suffix = '1' if period_number == '1' else '2'
        start_day = ICP.get_param(f'l10n_hn_hr_payroll.cutoff_start_day_{suffix}')
        end_day = ICP.get_param(f'l10n_hn_hr_payroll.cutoff_end_day_{suffix}')
        from_prev = ICP.get_param(f'l10n_hn_hr_payroll.cutoff_from_prev_month_{suffix}', 'True').lower() in ('true', '1', 'yes')
        if start_day is not None and end_day is not None:
            try:
                start_day = int(start_day)
                end_day = int(end_day)
            except (ValueError, TypeError):
                start_day = end_day = None
        if start_day is None or end_day is None:
            # Prioridad 2: Modelo l10n.hn.payroll.cutoff.config
            config = self.search([
                ('company_id', '=', payroll_period.company_id.id),
                ('year', '=', year),
                ('period_number', '=', period_number),
            ], limit=1)
            if not config:
                return None, None
            start_day = config.cutoff_start_day
            end_day = config.cutoff_end_day
            from_prev = config.cutoff_from_previous_month
        # Calcular fechas (start_day, end_day, from_prev ya definidos arriba)
        if from_prev:
            prev_month = month - 1 if month > 1 else 12
            prev_year = year if month > 1 else year - 1
            last_prev = monthrange(prev_year, prev_month)[1]
            date_from = date(prev_year, prev_month, min(start_day, last_prev))
        else:
            date_from = date(year, month, min(start_day, monthrange(year, month)[1]))
        if period_number == '2':
            last_curr = monthrange(year, month)[1]
            date_to = date(year, month, min(end_day, last_curr))
        else:
            date_to = date(year, month, min(end_day, monthrange(year, month)[1]))
        return date_from, date_to
