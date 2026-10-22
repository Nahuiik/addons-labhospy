# -*- coding: utf-8 -*-
"""Alertas inteligentes (V20 Fase 6, #21).

Modelo doble:

- ``gn.financial.dashboard.alert.rule``: define reglas configurables
  (un KPI, un operador y un umbral). Pueden ser nativas (instaladas via
  data) o creadas por el usuario.
- ``gn.financial.dashboard.alert.event``: instancia generada cuando una
  regla dispara para una compañía. Tiene estado (open / ack / resolved)
  y guarda contexto serializable para auditoría y drill-down.

El motor de evaluación (``_evaluate_alerts`` en ``alert_engine.py``)
combina las reglas configurables con señales derivadas (variaciones
bruscas, score predictivo, concentración de cartera, objetivos
incumplidos) en un único stream.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


KPI_CHOICES = [
    ('gross_margin', 'Margen bruto (%)'),
    ('operating_margin', 'Margen operativo (%)'),
    ('ebitda_margin', 'Margen EBITDA (%)'),
    ('net_margin', 'Margen neto (%)'),
    ('current_ratio', 'Razón corriente'),
    ('quick_ratio', 'Prueba ácida'),
    ('debt_to_assets', 'Deuda / Activos'),
    ('interest_coverage', 'Cobertura de intereses'),
    ('inventory_turnover', 'Rotación de inventario'),
    ('asset_turnover', 'Rotación de activos'),
    ('dso_days', 'Días de cartera (DSO)'),
    ('dpo_days', 'Días de pago (DPO)'),
    ('cash_surplus', 'Superávit de caja del periodo'),
    ('closing_bank', 'Saldo de caja al cierre'),
    ('working_capital', 'Capital de trabajo'),
    ('predictive_score', 'Score predictivo (0-100)'),
    ('overdue_pct', 'Mora de cartera (%)'),
    ('customer_concentration_pct', 'Concentración top-1 cliente (%)'),
    ('supplier_concentration_pct', 'Dependencia top-1 proveedor (%)'),
]

OPERATORS = [
    ('lt', '<'),
    ('lte', '≤'),
    ('gt', '>'),
    ('gte', '≥'),
    ('between', 'entre [min, max]'),
    ('outside', 'fuera de [min, max]'),
]

SEVERITIES = [
    ('info', 'Informativa'),
    ('warning', 'Advertencia'),
    ('critical', 'Crítica'),
]

CATEGORIES = [
    ('liquidity', 'Liquidez'),
    ('profitability', 'Rentabilidad'),
    ('working_capital', 'Capital de trabajo'),
    ('risk', 'Riesgo'),
    ('growth', 'Crecimiento'),
    ('other', 'Otras'),
]


class GnFinancialDashboardAlertRule(models.Model):
    _name = 'gn.financial.dashboard.alert.rule'
    _description = 'Regla de alerta del Tablero Financiero'
    _order = 'sequence, severity desc, name'

    name = fields.Char(string='Nombre', required=True, translate=True)
    code = fields.Char(string='Código', required=True,
                       help='Identificador único usado por el motor para de-duplicar.')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Compañía',
                                 default=lambda s: s.env.company, ondelete='cascade')
    kpi = fields.Selection(KPI_CHOICES, string='KPI', required=True)
    operator = fields.Selection(OPERATORS, string='Operador', required=True, default='lt')
    threshold = fields.Float(string='Umbral')
    threshold_max = fields.Float(string='Umbral máximo',
                                 help='Solo para operadores between / outside.')
    severity = fields.Selection(SEVERITIES, default='warning', required=True)
    category = fields.Selection(CATEGORIES, default='other', required=True)
    message_template = fields.Text(
        string='Mensaje',
        translate=True,
        help='Texto mostrado al usuario. Soporta placeholders: '
             '{value}, {threshold}, {threshold_max}, {kpi_label}, {company}.',
    )
    action_hint = fields.Text(
        string='Acción sugerida',
        translate=True,
        help='Texto breve recomendando la acción a tomar.',
    )
    # Compat con la pestaña de Decisiones (#22): cuando una regla
    # dispara, su entrada se transforma en una "decisión" con esta
    # categoría/prioridad.
    decision_priority = fields.Integer(
        string='Prioridad en Decisiones', default=50,
        help='0-100. Cuanto más alto, más arriba aparece en el centro de decisiones.',
    )

    _code_company_uniq = models.Constraint(
        'unique(code, company_id)',
        'El código de la regla de alerta debe ser único por compañía.',
    )

    @api.constrains('operator', 'threshold_max', 'threshold')
    def _check_range(self):
        for r in self:
            if r.operator in ('between', 'outside'):
                if r.threshold_max in (False, 0.0) and r.threshold in (False, 0.0):
                    continue  # Permitimos defaults nulos pero el motor los ignora.
                if r.threshold_max < r.threshold:
                    raise ValidationError(_(
                        'En operadores "entre" / "fuera de" el máximo debe ser '
                        '≥ al mínimo.'
                    ))

    def evaluate(self, value):
        """Devuelve True si la regla dispara con ``value``."""
        self.ensure_one()
        if value is None:
            return False
        t = self.threshold
        tmax = self.threshold_max
        op = self.operator
        if op == 'lt':
            return value < t
        if op == 'lte':
            return value <= t
        if op == 'gt':
            return value > t
        if op == 'gte':
            return value >= t
        if op == 'between':
            return t <= value <= tmax
        if op == 'outside':
            return value < t or value > tmax
        return False

    def render_message(self, value, company):
        labels = dict(KPI_CHOICES)
        # Formato con coma de miles + punto decimal; el número de
        # decimales se decide según el rango del KPI (ratios y días
        # van con menos decimales que los montos monetarios).
        decimals = self._format_decimals_for_kpi()
        ctx = {
            'value': self._fmt_num(value, decimals),
            'threshold': self._fmt_num(self.threshold, decimals),
            'threshold_max': self._fmt_num(self.threshold_max, decimals),
            'kpi_label': labels.get(self.kpi, self.kpi),
            'company': company.display_name if company else '',
        }
        tpl = self.message_template or _(
            '{kpi_label}: {value} (umbral {threshold}).'
        )
        try:
            return tpl.format(**ctx)
        except (KeyError, IndexError):
            return tpl

    def _format_decimals_for_kpi(self):
        """KPIs en porcentaje y en días usan 1 / 0 decimales; el resto 2."""
        if self.kpi in ('dso_days', 'dpo_days'):
            return 0
        if self.kpi in ('gross_margin', 'operating_margin', 'ebitda_margin',
                        'net_margin', 'overdue_pct', 'customer_concentration_pct',
                        'supplier_concentration_pct'):
            return 1
        if self.kpi in ('current_ratio', 'quick_ratio', 'debt_to_assets',
                        'interest_coverage', 'inventory_turnover',
                        'asset_turnover', 'predictive_score'):
            return 2
        return 2

    @staticmethod
    def _fmt_num(value, decimals=2):
        try:
            return ('{:,.%df}' % decimals).format(float(value or 0.0))
        except (ValueError, TypeError):
            return str(value)


class GnFinancialDashboardAlertEvent(models.Model):
    _name = 'gn.financial.dashboard.alert.event'
    _description = 'Evento de alerta del Tablero Financiero'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread']

    name = fields.Char(string='Resumen', required=True, tracking=True)
    rule_id = fields.Many2one('gn.financial.dashboard.alert.rule',
                              string='Regla', ondelete='set null')
    code = fields.Char(string='Código', index=True,
                       help='De-duplicación: una regla genera un único evento abierto.')
    company_id = fields.Many2one('res.company', required=True,
                                 default=lambda s: s.env.company, ondelete='cascade')
    severity = fields.Selection(SEVERITIES, default='warning', required=True, tracking=True)
    category = fields.Selection(CATEGORIES, default='other', required=True)
    state = fields.Selection([
        ('open', 'Abierta'),
        ('ack', 'Reconocida'),
        ('resolved', 'Resuelta'),
        ('snoozed', 'Pospuesta'),
    ], default='open', required=True, tracking=True)
    date = fields.Datetime(default=fields.Datetime.now, required=True, tracking=True)
    date_ack = fields.Datetime(tracking=True)
    date_resolved = fields.Datetime(tracking=True)
    snoozed_until = fields.Datetime(string='Pospuesta hasta', tracking=True)
    user_ack_id = fields.Many2one('res.users', string='Reconocida por', tracking=True)
    user_resolved_id = fields.Many2one('res.users', string='Resuelta por', tracking=True)
    note = fields.Text(string='Notas')
    # Contexto enriquecido para drill-down desde el frontend.
    kpi_value = fields.Float(string='Valor del KPI')
    threshold = fields.Float(string='Umbral configurado')
    action_hint = fields.Text(string='Acción sugerida')
    payload = fields.Text(
        string='Payload JSON',
        help='Información adicional serializable (texto plano).',
    )

    # Nota: la de-duplicación "una sola alerta abierta por (code, company)"
    # se maneja en ``_evaluate_alerts`` (alert_engine.py). Un EXCLUDE
    # parcial PostgreSQL nativo no está soportado por models.Constraint.

    def action_acknowledge(self, note=None):
        for r in self:
            if r.state == 'open':
                r.state = 'ack'
                r.user_ack_id = self.env.user
                r.date_ack = fields.Datetime.now()
                if note:
                    r.note = (r.note or '') + ('\n' if r.note else '') + note
                r.message_post(body=_('Alerta reconocida.'))
        return True

    def action_resolve(self, note=None):
        for r in self:
            if r.state in ('open', 'ack', 'snoozed'):
                r.state = 'resolved'
                r.user_resolved_id = self.env.user
                r.date_resolved = fields.Datetime.now()
                if note:
                    r.note = (r.note or '') + ('\n' if r.note else '') + note
                r.message_post(body=_('Alerta resuelta.'))
        return True

    def action_snooze(self, until):
        for r in self:
            r.state = 'snoozed'
            r.snoozed_until = until
            r.message_post(body=_('Alerta pospuesta hasta %s.') % until)
        return True
