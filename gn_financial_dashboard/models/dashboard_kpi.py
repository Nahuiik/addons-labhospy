# -*- coding: utf-8 -*-
"""Constructor de KPIs personalizados (V20 Fase 2, #1).

Permite a un gerente contable definir indicadores propios sin escribir código.
El motor reusa los mismos cálculos del dashboard y respeta los filtros activos
(compañía, fechas, diarios, sucursal, centro de costos, proyecto).

Tipos de fórmula soportados: balance directo de cuentas, suma por tipo de
cuenta, razón entre dos componentes y expresión aritmética sobre otros KPIs.
"""
import ast
import operator
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError


FORMULA_TYPES = [
    ('account_balance', 'Balance de cuentas (lista de cuentas)'),
    ('account_type_sum', 'Suma por tipo de cuenta'),
    ('ratio', 'Razón (numerador / denominador)'),
    ('expression', 'Expresión sobre otros KPIs'),
]
PERIOD_MODES = [
    ('range', 'Movimientos del rango'),
    ('asof', 'Saldo acumulado al corte'),
]
SIGN_MODES = [
    ('natural', 'Natural (débito − crédito)'),
    ('debit', 'Solo débito'),
    ('credit', 'Solo crédito'),
    ('invert', 'Invertido (crédito − débito)'),
]
FORMAT_MODES = [
    ('money', 'Monto'),
    ('percent', 'Porcentaje'),
    ('ratio', 'Razón (sin formato)'),
    ('days', 'Días'),
    ('number', 'Número'),
]
TREND_MODES = [
    ('higher_better', 'Mayor es mejor'),
    ('lower_better', 'Menor es mejor'),
    ('neutral', 'Neutro'),
]


# Tipos de cuenta válidos (alineados con Odoo 19).
ACCOUNT_TYPE_KEYS = [
    'income', 'income_other',
    'expense', 'expense_direct_cost', 'expense_depreciation',
    'asset_cash', 'asset_receivable', 'asset_current',
    'asset_prepayments', 'asset_fixed', 'asset_non_current',
    'liability_payable', 'liability_credit_card',
    'liability_current', 'liability_non_current',
    'equity', 'equity_unaffected',
    'off_balance',
]


class GnFinancialDashboardKpi(models.Model):
    _name = 'gn.financial.dashboard.kpi'
    _description = 'KPI personalizado del Tablero Financiero'
    _order = 'sequence, name'

    name = fields.Char(string='Nombre', required=True, translate=True)
    code = fields.Char(
        string='Código', required=True,
        help='Identificador único (sin espacios). Útil para referenciar este '
             'KPI desde una expresión de otro KPI.',
    )
    description = fields.Text(string='Descripción')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company,
        help='Compañía a la que aplica el KPI. Solo es visible en esta compañía.',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    category = fields.Selection(
        [('profitability', 'Rentabilidad'),
         ('liquidity', 'Liquidez'),
         ('cashflow', 'Flujo de caja'),
         ('aging', 'Cartera'),
         ('balance', 'Balance'),
         ('custom', 'Personalizado')],
        default='custom', string='Categoría',
    )
    icon = fields.Char(
        string='Icono',
        default='fa-bullseye',
        help='Clase Font Awesome (p.ej. fa-line-chart).',
    )
    show_in_overview = fields.Boolean(
        string='Mostrar en Resumen',
        default=False,
        help='Si está activo, aparece como tarjeta KPI en la pestaña Resumen.',
    )
    show_in_my_kpis = fields.Boolean(
        string='Mostrar en "Mis KPIs"',
        default=True,
        help='Aparece en la pestaña Mis KPIs (tablero de KPIs personalizados).',
    )

    # ------------------------------------------------------------------
    # Fórmula
    # ------------------------------------------------------------------
    formula_type = fields.Selection(
        FORMULA_TYPES, string='Tipo de fórmula', required=True,
        default='account_type_sum',
    )
    period_mode = fields.Selection(
        PERIOD_MODES, string='Periodo', default='range',
        help='"Movimientos del rango" suma débito/crédito entre las fechas; '
             '"Saldo acumulado al corte" usa el saldo a la fecha final.',
    )
    sign_mode = fields.Selection(
        SIGN_MODES, string='Signo', default='natural',
        help='Cómo agregar los saldos: natural (balance), solo débito, solo '
             'crédito, o invertido. Para cuentas de ingreso suele usarse '
             '"Invertido" para que el resultado quede positivo.',
    )

    # Variante 1 / 2: cuentas explícitas o tipos de cuenta.
    account_ids = fields.Many2many(
        'account.account',
        relation='gn_fd_kpi_account_rel',
        column1='kpi_id', column2='account_id',
        string='Cuentas',
        help='Cuentas contables para la suma. Solo aplica cuando el tipo de '
             'fórmula es "Balance de cuentas".',
    )
    account_type_keys = fields.Char(
        string='Tipos de cuenta',
        help='Lista de account_type separados por coma. Ej.: income,income_other.',
    )

    # Variante 3 (ratio): subcomponentes.
    numerator_kind = fields.Selection(
        [('account_balance', 'Balance de cuentas'),
         ('account_type_sum', 'Tipos de cuenta')],
        string='Numerador (tipo)', default='account_type_sum',
    )
    numerator_account_ids = fields.Many2many(
        'account.account',
        relation='gn_fd_kpi_num_account_rel',
        column1='kpi_id', column2='account_id',
        string='Numerador: cuentas',
    )
    numerator_type_keys = fields.Char(string='Numerador: tipos de cuenta')
    numerator_sign = fields.Selection(SIGN_MODES, string='Numerador: signo',
                                      default='natural')

    denominator_kind = fields.Selection(
        [('account_balance', 'Balance de cuentas'),
         ('account_type_sum', 'Tipos de cuenta')],
        string='Denominador (tipo)', default='account_type_sum',
    )
    denominator_account_ids = fields.Many2many(
        'account.account',
        relation='gn_fd_kpi_den_account_rel',
        column1='kpi_id', column2='account_id',
        string='Denominador: cuentas',
    )
    denominator_type_keys = fields.Char(string='Denominador: tipos de cuenta')
    denominator_sign = fields.Selection(SIGN_MODES, string='Denominador: signo',
                                        default='natural')
    percent_multiplier = fields.Boolean(
        string='Multiplicar por 100',
        default=False,
        help='Útil para razones expresadas en porcentaje (margen, etc.).',
    )

    # Variante 4: expresión.
    expression = fields.Char(
        string='Expresión',
        help='Aritmética simple con códigos de KPIs nativos o personalizados. '
             'Ej.: revenue - cogs, net_profit / total_assets * 100.',
    )

    # ------------------------------------------------------------------
    # Presentación y alertas
    # ------------------------------------------------------------------
    format_mode = fields.Selection(FORMAT_MODES, default='money',
                                    string='Formato')
    decimal_places = fields.Integer(default=2, string='Decimales')
    trend_mode = fields.Selection(TREND_MODES, default='higher_better',
                                  string='Dirección deseada')
    target_value = fields.Float(string='Meta', default=0.0,
                                help='Valor objetivo (opcional).')
    warning_threshold = fields.Float(
        string='Umbral de alerta',
        default=0.0,
        help='Cuando el KPI cae por debajo (mayor=mejor) o sube por encima '
             '(menor=mejor), se marca con advertencia.',
    )

    _code_company_uniq = models.Constraint(
        'unique(code, company_id)',
        'El código del KPI debe ser único por compañía.',
    )

    @api.constrains('code')
    def _check_code(self):
        for rec in self:
            if not rec.code:
                continue
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', rec.code):
                raise ValidationError(_(
                    'El código solo puede contener letras, números y guión bajo, '
                    'y debe iniciar con letra o guión bajo.'
                ))

    @api.constrains('account_type_keys', 'numerator_type_keys', 'denominator_type_keys')
    def _check_account_types(self):
        valid = set(ACCOUNT_TYPE_KEYS)
        for rec in self:
            for fname in ('account_type_keys', 'numerator_type_keys',
                          'denominator_type_keys'):
                raw = rec[fname]
                if not raw:
                    continue
                keys = [k.strip() for k in (raw or '').split(',') if k.strip()]
                bad = [k for k in keys if k not in valid]
                if bad:
                    raise ValidationError(_(
                        '%(field)s: tipo(s) no válido(s): %(bad)s.\nValores '
                        'permitidos: %(valid)s',
                        field=fname, bad=', '.join(bad),
                        valid=', '.join(sorted(valid))
                    ))

    @api.constrains('formula_type', 'account_ids', 'account_type_keys',
                    'numerator_kind', 'denominator_kind', 'expression')
    def _check_formula_completeness(self):
        for rec in self:
            if rec.formula_type == 'account_balance' and not rec.account_ids:
                raise ValidationError(_('Debes seleccionar al menos una cuenta.'))
            if rec.formula_type == 'account_type_sum' and not (rec.account_type_keys or '').strip():
                raise ValidationError(_('Debes indicar al menos un tipo de cuenta.'))
            if rec.formula_type == 'ratio':
                if rec.numerator_kind == 'account_balance' and not rec.numerator_account_ids:
                    raise ValidationError(_('Numerador: faltan cuentas.'))
                if rec.numerator_kind == 'account_type_sum' and not (rec.numerator_type_keys or '').strip():
                    raise ValidationError(_('Numerador: faltan tipos de cuenta.'))
                if rec.denominator_kind == 'account_balance' and not rec.denominator_account_ids:
                    raise ValidationError(_('Denominador: faltan cuentas.'))
                if rec.denominator_kind == 'account_type_sum' and not (rec.denominator_type_keys or '').strip():
                    raise ValidationError(_('Denominador: faltan tipos de cuenta.'))
            if rec.formula_type == 'expression' and not (rec.expression or '').strip():
                raise ValidationError(_('Debes escribir una expresión.'))

    # ------------------------------------------------------------------
    # Evaluación segura de expresiones (solo +,-,*,/,paréntesis, números y
    # nombres de KPIs disponibles en el contexto). No usa eval ni globals.
    # ------------------------------------------------------------------
    _ALLOWED_BIN_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
    }
    _ALLOWED_UN_OPS = {
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    @api.model
    def _safe_eval(self, expression, env_values):
        """Evalúa la expresión con un set restringido de nodos AST.

        ``env_values`` mapea nombre → valor numérico. Cualquier otro nombre o
        nodo no permitido lanza UserError.
        """
        try:
            tree = ast.parse(expression, mode='eval')
        except SyntaxError as e:
            raise UserError(_('Expresión inválida: %s') % e)

        def _eval(node):
            if isinstance(node, ast.Expression):
                return _eval(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return float(node.value)
            if isinstance(node, ast.Name):
                if node.id not in env_values:
                    raise UserError(_(
                        'Variable desconocida en la expresión: %s') % node.id)
                return float(env_values[node.id] or 0.0)
            if isinstance(node, ast.BinOp) and type(node.op) in self._ALLOWED_BIN_OPS:
                left = _eval(node.left)
                right = _eval(node.right)
                if isinstance(node.op, ast.Div) and not right:
                    return 0.0
                return self._ALLOWED_BIN_OPS[type(node.op)](left, right)
            if isinstance(node, ast.UnaryOp) and type(node.op) in self._ALLOWED_UN_OPS:
                return self._ALLOWED_UN_OPS[type(node.op)](_eval(node.operand))
            raise UserError(_('Operación no permitida en la expresión.'))

        return _eval(tree)

    # ------------------------------------------------------------------
    # Acción de previsualización (usada desde el form)
    # ------------------------------------------------------------------
    def action_preview(self):
        """Calcula el KPI con los filtros por defecto y lo muestra en notificación."""
        self.ensure_one()
        Dash = self.env['gn.financial.dashboard']
        opts = Dash.get_filter_options(company_id=self.company_id.id)
        result = Dash._evaluate_custom_kpi(
            self, {'company_id': self.company_id.id,
                   'date_from': opts['date_from'], 'date_to': opts['date_to']},
        )
        msg = _('%(name)s: %(value)s') % {
            'name': self.name,
            'value': self.env['gn.financial.dashboard']._format_kpi_value(
                result['value'], self.format_mode, self.decimal_places,
                self.company_id.currency_id,
            ),
        }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success' if result['value'] else 'info',
                'title': _('Previsualización del KPI'),
                'message': msg,
                'sticky': False,
            },
        }
