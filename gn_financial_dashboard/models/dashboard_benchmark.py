# -*- coding: utf-8 -*-
"""Benchmarks sectoriales para comparar KPIs contra valores de referencia.

El modelo es deliberadamente simple: cada registro define el objetivo y
la tolerancia esperada de un KPI dentro de un sector. El cálculo de
brecha y semáforo se hace en ``_compare_kpi_to_benchmark`` (en el
módulo predictivo) reutilizando los KPIs ya computados.

Los datos demo (cargados en ``data/benchmark_data.xml``) cubren los
sectores más relevantes para LABHOSPY (hospital/clínica, laboratorio,
distribución de insumos, servicios). Si la organización opera en otro
sector, basta con duplicar los registros y ajustar los valores.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


# Nota Odoo 19: NO usar ``_()`` en tiempo de import (no hay contexto de
# idioma y revienta el bootstrap). Los strings literales en
# Selection se extraen automáticamente al .pot por el comando i18n.
KPI_CODES = [
    ('gross_margin_pct', 'Margen bruto (%)'),
    ('operating_margin_pct', 'Margen operativo (%)'),
    ('ebitda_margin_pct', 'Margen EBITDA (%)'),
    ('net_margin_pct', 'Margen neto (%)'),
    ('current_ratio', 'Razón corriente'),
    ('quick_ratio', 'Prueba ácida'),
    ('debt_to_assets', 'Apalancamiento (Deuda/Activos)'),
    ('roa_pct', 'ROA (%)'),
    ('roe_pct', 'ROE (%)'),
    ('dso_days', 'Días de cartera (DSO)'),
    ('dpo_days', 'Días de pago a proveedores (DPO)'),
    ('inventory_turnover', 'Rotación de inventario'),
    ('asset_turnover', 'Rotación de activos'),
    ('interest_coverage', 'Cobertura de intereses'),
    ('revenue_growth_pct', 'Crecimiento de ingresos (%)'),
]

# Dirección preferida del KPI: 'higher_better' o 'lower_better'.
DIRECTIONS = [
    ('higher_better', 'Mayor es mejor'),
    ('lower_better', 'Menor es mejor'),
]


class GnFinancialDashboardBenchmark(models.Model):
    _name = 'gn.financial.dashboard.benchmark'
    _description = 'Benchmark sectorial del Tablero Financiero'
    _order = 'sector, kpi_code'

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True,
    )
    sector = fields.Char(
        string='Sector',
        required=True,
        help='Identificador libre del sector (hospital, laboratorio, retail…).',
    )
    sector_label = fields.Char(
        string='Etiqueta del sector',
        translate=True,
        help='Texto visible en el dashboard (p.ej. "Hospital privado").',
    )
    kpi_code = fields.Selection(
        KPI_CODES, string='KPI', required=True,
    )
    target_value = fields.Float(
        string='Valor objetivo', required=True,
        help='Valor mediano / benchmark esperado para el sector.',
    )
    min_value = fields.Float(
        string='Mínimo aceptable',
        help='Por debajo de este valor el KPI se considera en riesgo.',
    )
    max_value = fields.Float(
        string='Máximo aceptable',
        help='Por encima de este valor el KPI se considera en riesgo.',
    )
    direction = fields.Selection(
        DIRECTIONS, default='higher_better',
        string='Dirección preferida',
        required=True,
    )
    source = fields.Char(
        string='Fuente',
        help='Referencia, estudio o estimación de la cual proviene el dato.',
    )
    notes = fields.Text(string='Notas')
    company_id = fields.Many2one(
        'res.company', string='Compañía',
        default=lambda s: s.env.company,
        ondelete='cascade',
    )
    active = fields.Boolean(default=True)

    _kpi_sector_uniq = models.Constraint(
        'unique(sector, kpi_code, company_id)',
        'Ya existe un benchmark para este KPI en el sector indicado.',
    )

    @api.depends('sector', 'sector_label', 'kpi_code')
    def _compute_name(self):
        labels = dict(KPI_CODES)
        for r in self:
            sec = r.sector_label or r.sector or '—'
            kpi = labels.get(r.kpi_code, r.kpi_code or '—')
            r.name = '%s · %s' % (sec, kpi)

    @api.constrains('min_value', 'max_value', 'target_value')
    def _check_range(self):
        for r in self:
            if r.min_value and r.max_value and r.min_value > r.max_value:
                raise ValidationError(_(
                    'El mínimo aceptable no puede ser mayor que el máximo.'
                ))
