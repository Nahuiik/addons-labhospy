# -*- coding: utf-8 -*-
"""Presupuesto / metas financieras del Tablero.

Modelo editable (uno por compañía + año fiscal) con líneas mensuales por
categoría (ingresos, costo de ventas, gastos). Permite comparar el real
contra el presupuesto y calcular % de avance y desviaciones.

Es un modelo propio del companion (no toca ``account.budget`` ni el módulo
comercial), pensado para metas de alto nivel que alimentan la pestaña de
Planeación del tablero.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


# Categorías de presupuesto (alineadas con los grupos de KPIs del tablero).
BUDGET_CATEGORIES = [
    ('income', 'Ingresos'),
    ('cogs', 'Costo de ventas'),
    ('expenses', 'Gastos operativos'),
]


class GnFinancialDashboardBudget(models.Model):
    _name = 'gn.financial.dashboard.budget'
    _description = 'Presupuesto del Tablero Financiero'
    _order = 'year desc, company_id'

    name = fields.Char(
        string='Nombre', compute='_compute_name', store=True, readonly=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company, index=True, ondelete='cascade',
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id', string='Moneda', readonly=True,
    )
    year = fields.Integer(
        string='Año', required=True, index=True,
        default=lambda self: fields.Date.context_today(self).year,
    )
    active = fields.Boolean(default=True)
    line_ids = fields.One2many(
        'gn.financial.dashboard.budget.line', 'budget_id',
        string='Líneas', copy=True,
    )

    total_income = fields.Monetary(
        string='Meta ingresos', compute='_compute_totals', store=True,
        currency_field='currency_id',
    )
    total_cogs = fields.Monetary(
        string='Meta costo de ventas', compute='_compute_totals', store=True,
        currency_field='currency_id',
    )
    total_expenses = fields.Monetary(
        string='Meta gastos', compute='_compute_totals', store=True,
        currency_field='currency_id',
    )
    total_net = fields.Monetary(
        string='Meta utilidad neta', compute='_compute_totals', store=True,
        currency_field='currency_id',
    )

    _company_year_uniq = models.Constraint(
        'unique(company_id, year)',
        'Ya existe un presupuesto para esta compañía y año.',
    )

    @api.depends('company_id', 'year')
    def _compute_name(self):
        for rec in self:
            rec.name = _('Presupuesto %(year)s · %(company)s', year=rec.year,
                         company=rec.company_id.name or '')

    @api.depends('line_ids.amount', 'line_ids.category')
    def _compute_totals(self):
        for rec in self:
            totals = dict.fromkeys(('income', 'cogs', 'expenses'), 0.0)
            for line in rec.line_ids:
                if line.category in totals:
                    totals[line.category] += line.amount
            rec.total_income = totals['income']
            rec.total_cogs = totals['cogs']
            rec.total_expenses = totals['expenses']
            rec.total_net = totals['income'] - totals['cogs'] - totals['expenses']

    @api.constrains('year')
    def _check_year(self):
        for rec in self:
            if rec.year < 2000 or rec.year > 2100:
                raise ValidationError(_('El año del presupuesto no es válido.'))

    def action_generate_lines(self):
        """Crea (si faltan) las 12×3 líneas mensuales en cero para edición rápida."""
        Line = self.env['gn.financial.dashboard.budget.line']
        for rec in self:
            existing = {(l.month, l.category) for l in rec.line_ids}
            vals = []
            for category, _label in BUDGET_CATEGORIES:
                for month in range(1, 13):
                    if (month, category) not in existing:
                        vals.append({
                            'budget_id': rec.id,
                            'month': month,
                            'category': category,
                            'amount': 0.0,
                        })
            if vals:
                Line.create(vals)
        return True

    @api.model
    def get_or_create(self, company, year):
        budget = self.sudo().search([
            ('company_id', '=', company.id), ('year', '=', year),
        ], limit=1)
        if not budget:
            budget = self.sudo().create({'company_id': company.id, 'year': year})
            budget.action_generate_lines()
        return budget

    def monthly_matrix(self):
        """Devuelve {category: [12 montos]} para consumo del tablero."""
        self.ensure_one()
        matrix = {cat: [0.0] * 12 for cat, _l in BUDGET_CATEGORIES}
        for line in self.line_ids:
            if line.category in matrix and 1 <= line.month <= 12:
                matrix[line.category][line.month - 1] += line.amount
        return matrix


class GnFinancialDashboardBudgetLine(models.Model):
    _name = 'gn.financial.dashboard.budget.line'
    _description = 'Línea de presupuesto del Tablero Financiero'
    _order = 'category, month'

    budget_id = fields.Many2one(
        'gn.financial.dashboard.budget', string='Presupuesto',
        required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(
        related='budget_id.company_id', store=True, index=True,
    )
    currency_id = fields.Many2one(
        related='budget_id.currency_id', readonly=True,
    )
    month = fields.Integer(string='Mes', required=True, help='1 = Enero … 12 = Diciembre')
    category = fields.Selection(
        BUDGET_CATEGORIES, string='Categoría', required=True,
    )
    amount = fields.Monetary(
        string='Meta', currency_field='currency_id', default=0.0,
    )

    @api.constrains('month')
    def _check_month(self):
        for rec in self:
            if not (1 <= rec.month <= 12):
                raise ValidationError(_('El mes debe estar entre 1 y 12.'))
