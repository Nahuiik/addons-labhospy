# -*- coding: utf-8 -*-
"""Objetivos estratégicos del Tablero Financiero (V20 Fase 2, #19).

Permite definir metas medibles sobre KPIs nativos del dashboard (revenue,
net_profit, etc.) o sobre KPIs personalizados creados con el constructor.
El motor calcula el progreso vs. meta y el estado (en curso, alcanzado,
desviado, vencido) sin almacenar valores precalculados (se recalcula al pedir
``get_goals_progress``).
"""
from odoo import _, api, fields, models


KPI_NATIVE_KEYS = [
    ('revenue', 'Ingresos'),
    ('cogs', 'Costo de ventas'),
    ('gross_profit', 'Utilidad bruta'),
    ('expenses', 'Gastos'),
    ('net_profit', 'Utilidad neta'),
    ('gross_margin', 'Margen bruto (%)'),
    ('net_margin', 'Margen neto (%)'),
    ('roi', 'ROI (%)'),
    ('roa', 'ROA (%)'),
    ('roe', 'ROE (%)'),
    ('ebit', 'EBIT'),
    ('ebitda', 'EBITDA'),
    ('ebitda_margin', 'Margen EBITDA (%)'),
    ('operating_margin', 'Margen operativo (%)'),
    ('cash_surplus', 'Flujo de caja'),
    ('closing_bank', 'Saldo bancario'),
    ('receivables', 'Cuentas por cobrar'),
    ('payables', 'Cuentas por pagar'),
    ('working_capital', 'Capital de trabajo'),
    ('current_ratio', 'Razón corriente'),
    ('quick_ratio', 'Prueba ácida'),
    ('assets_turnover', 'Rotación de activos'),
    ('ar_turnover', 'Rotación de CxC'),
    ('ap_turnover', 'Rotación de CxP'),
    ('inventory_turnover', 'Rotación de inventarios'),
    ('leverage_ratio', 'Apalancamiento'),
    ('interest_coverage', 'Cobertura de intereses'),
]
DIRECTION = [
    ('above', 'Alcanzar o superar la meta'),
    ('below', 'Mantenerse por debajo de la meta'),
]


class GnFinancialDashboardGoal(models.Model):
    _name = 'gn.financial.dashboard.goal'
    _description = 'Objetivo estratégico (Tablero Financiero)'
    _order = 'date_deadline, name'

    name = fields.Char(string='Nombre', required=True, translate=True)
    description = fields.Text(string='Descripción')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company,
    )
    owner_id = fields.Many2one(
        'res.users', string='Responsable',
        default=lambda self: self.env.user,
    )

    # Referencia al KPI: nativo (string) o personalizado (Many2one).
    kpi_source = fields.Selection(
        [('native', 'KPI del sistema'), ('custom', 'KPI personalizado')],
        string='Fuente del KPI', default='native', required=True,
    )
    kpi_key = fields.Selection(
        KPI_NATIVE_KEYS, string='KPI del sistema',
    )
    custom_kpi_id = fields.Many2one(
        'gn.financial.dashboard.kpi', string='KPI personalizado',
        domain="[('company_id', '=', company_id)]",
    )

    direction = fields.Selection(DIRECTION, default='above', required=True,
                                  string='Dirección')
    target_value = fields.Float(string='Meta', required=True)
    date_start = fields.Date(string='Inicio', default=fields.Date.today)
    date_deadline = fields.Date(string='Fecha límite')
    weight = fields.Integer(
        string='Peso',
        default=10,
        help='Para ordenar / priorizar varios objetivos.',
    )
    active = fields.Boolean(default=True)

    @api.constrains('kpi_source', 'kpi_key', 'custom_kpi_id')
    def _check_kpi(self):
        for rec in self:
            if rec.kpi_source == 'native' and not rec.kpi_key:
                raise models.ValidationError(_(
                    'Selecciona un KPI del sistema.'))
            if rec.kpi_source == 'custom' and not rec.custom_kpi_id:
                raise models.ValidationError(_(
                    'Selecciona un KPI personalizado.'))

    def to_payload(self):
        """Serializa el objetivo (sin progreso, lo añade el RPC)."""
        self.ensure_one()
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description or '',
            'kpi_source': self.kpi_source,
            'kpi_key': self.kpi_key,
            'custom_kpi_id': self.custom_kpi_id.id if self.custom_kpi_id else False,
            'kpi_label': (
                dict(KPI_NATIVE_KEYS).get(self.kpi_key, self.kpi_key)
                if self.kpi_source == 'native'
                else (self.custom_kpi_id.name or '')
            ),
            'direction': self.direction,
            'target_value': self.target_value,
            'date_start': fields.Date.to_string(self.date_start) if self.date_start else False,
            'date_deadline': fields.Date.to_string(self.date_deadline) if self.date_deadline else False,
            'owner_id': self.owner_id.id,
            'owner_name': self.owner_id.display_name,
            'weight': self.weight,
        }

    def evaluate_status(self, current_value):
        """Calcula estado y progreso a partir de un valor actual."""
        target = self.target_value or 0.0
        cur = float(current_value or 0.0)
        if self.direction == 'above':
            progress = (cur / target * 100.0) if target else 0.0
            attained = cur >= target
        else:
            # below: mientras menor, mejor. 100% si <= target.
            progress = (target / cur * 100.0) if cur else 100.0
            attained = cur <= target
        progress = max(min(round(progress, 1), 999.0), -999.0)
        status = 'attained' if attained else 'in_progress'
        if self.date_deadline and self.date_deadline < fields.Date.context_today(self):
            status = 'attained' if attained else 'overdue'
        return {
            'current_value': round(cur, 2),
            'progress': progress,
            'attained': attained,
            'status': status,
        }
