# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sales_default_period = fields.Selection([
        ('this_month', 'Mes actual'),
        ('last_30', 'Últimos 30 días'),
        ('this_quarter', 'Trimestre actual'),
    ], string='Período predeterminado')
    sales_forecast_method = fields.Selection([
        ('linear', 'Tendencia lineal'),
        ('moving_avg', 'Promedio móvil'),
        ('exp_smoothing', 'Suavizado exponencial'),
        ('daily_pace', 'Ritmo diario'),
    ], string='Método de pronóstico')
    sales_margin_min_pct = fields.Float(string='Margen mínimo (%)')
    sales_concentration_max_pct = fields.Float(string='Concentración máxima (%)')
    sales_inactive_customer_days = fields.Integer(string='Días cliente inactivo')

    def _sales_config(self):
        return self.env['sales.dashboard.config'].get_for_company(self.company_id)

    @api.model
    def get_values(self):
        res = super().get_values()
        cfg = self.env['sales.dashboard.config'].get_for_company(self.env.company)
        res.update({
            'sales_default_period': cfg.default_period,
            'sales_forecast_method': cfg.forecast_method,
            'sales_margin_min_pct': cfg.margin_min_pct,
            'sales_concentration_max_pct': cfg.concentration_max_pct,
            'sales_inactive_customer_days': cfg.inactive_customer_days,
        })
        return res

    def set_values(self):
        super().set_values()
        cfg = self._sales_config()
        cfg.write({
            'default_period': self.sales_default_period or cfg.default_period,
            'forecast_method': self.sales_forecast_method or cfg.forecast_method,
            'margin_min_pct': self.sales_margin_min_pct,
            'concentration_max_pct': self.sales_concentration_max_pct,
            'inactive_customer_days': self.sales_inactive_customer_days,
        })
