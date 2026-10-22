# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SalesDashboardConfig(models.Model):
    _name = 'sales.dashboard.config'
    _description = 'Configuración del dashboard de ventas'
    _rec_name = 'company_id'

    company_id = fields.Many2one('res.company', required=True, ondelete='cascade')
    default_period = fields.Selection([
        ('this_month', 'Mes actual'),
        ('last_30', 'Últimos 30 días'),
        ('this_quarter', 'Trimestre actual'),
    ], default='this_month')
    forecast_method = fields.Selection([
        ('linear', 'Tendencia lineal'),
        ('moving_avg', 'Promedio móvil'),
        ('exp_smoothing', 'Suavizado exponencial'),
        ('daily_pace', 'Ritmo diario'),
    ], default='linear', string='Método de pronóstico')
    margin_min_pct = fields.Float(string='Margen mínimo (%)', default=15.0)
    concentration_max_pct = fields.Float(string='Concentración máxima (%)', default=40.0)
    inactive_customer_days = fields.Integer(string='Días cliente inactivo', default=90)
    stalled_opportunity_days = fields.Integer(string='Días oportunidad estancada', default=30)
    rfm_recency_days = fields.Integer(string='RFM recencia (días)', default=90)
    # Pesos Sales Health Score (suma recomendada 100)
    weight_growth = fields.Float(default=15.0)
    weight_target = fields.Float(default=15.0)
    weight_margin = fields.Float(default=15.0)
    weight_conversion = fields.Float(default=10.0)
    weight_concentration = fields.Float(default=10.0)
    weight_returns = fields.Float(default=10.0)
    weight_pipeline = fields.Float(default=10.0)
    weight_recurring = fields.Float(default=10.0)
    weight_ticket = fields.Float(default=5.0)
    weight_activity = fields.Float(default=10.0)

    @api.constrains('company_id')
    def _check_company_unique(self):
        for rec in self:
            if self.search_count([('company_id', '=', rec.company_id.id), ('id', '!=', rec.id)]):
                raise ValidationError(_('Solo puede existir una configuración por compañía.'))

    @api.model
    def get_for_company(self, company):
        config = self.search([('company_id', '=', company.id)], limit=1)
        if not config:
            config = self.create({'company_id': company.id})
        return config
