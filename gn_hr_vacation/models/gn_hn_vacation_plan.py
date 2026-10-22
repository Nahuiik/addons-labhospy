# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

from odoo import fields, models


class GnHnVacationPlan(models.Model):
    _name = 'gn.hn.vacation.plan'
    _description = 'Plan de vacaciones'

    name = fields.Char('Nombre', required=True, translate=True)
    code = fields.Char('Código', required=True)
    rule_ids = fields.One2many(
        'gn.hn.vacation.rule',
        'plan_id',
        string='Reglas de antigüedad',
        copy=True,
    )
    leave_type_id = fields.Many2one(
        'hr.leave.type',
        string='Tipo de ausencia',
        help='Tipo de ausencia asociado a este plan',
        check_company=True,
    )
    is_temporary = fields.Boolean(
        'Es para personal temporal',
        default=False,
        help='Indica si aplica a empleados temporales/eventuales',
    )
    allow_proportional = fields.Boolean(
        'Permitir proporcional',
        default=False,
        help='Permite vacaciones proporcionales para temporales que no completan el año',
    )
    vacation_accrual_mode = fields.Selection(
        selection=[
            ('annual', 'Anual'),
            ('monthly', 'Mensual'),
            ('daily', 'Diario'),
        ],
        string='Forma de acumulación y asignación',
        default='annual',
        required=True,
        help='Anual: no hay asignación hasta el primer aniversario laboral; después un cupo completo por cada año '
             'cumplido según reglas de antigüedad (sin devengo mensual previo al primer aniversario). '
             'Mensual: una asignación por año laboral desde la fecha de ingreso al contrato; el número de días sube '
             'cada mes dentro de esa misma asignación. '
             'Diario: una asignación por año laboral desde el ingreso; el número de días sube cada día en esa misma '
             'asignación, en función de la duración real del período hasta el siguiente aniversario.',
    )
    vacation_year_basis = fields.Selection(
        selection=[
            ('labor', 'Año laboral (desde ingreso / aniversarios)'),
            ('civil', 'Año calendario (1 ene – 31 dic)'),
        ],
        string='Base del período vacacional',
        default='labor',
        required=True,
        help='Año laboral: cortes según fecha de ingreso y aniversarios laborales. '
             'Año calendario: cada período es del 1 de enero al 31 de diciembre (el primer o último año puede ser '
             'parcial respecto al ingreso).',
    )
    vacation_allocation_scope = fields.Selection(
        selection=[
            ('all', 'Todos los períodos (histórico)'),
            ('current', 'Solo el período vigente'),
        ],
        string='Alcance de asignaciones',
        default='all',
        required=True,
        help='Histórico: se mantienen asignaciones por cada período (año laboral o año civil) hasta la fecha. '
             'Solo período vigente: únicamente el período que contiene la fecha de hoy (p. ej. desde el último '
             'aniversario o el año civil en curso), sin crear filas de períodos anteriores en la sincronización.',
    )
    allow_monthly_proportional = fields.Boolean(
        'Acumulación mensual proporcional',
        default=False,
        help='Obsoleto en la localización HN (l10n_hn_hr_payroll): con forma «Anual» no se devenga nada antes del '
             'primer aniversario laboral. Se mantiene el campo por compatibilidad de vistas y datos.',
    )
    max_accumulation_periods = fields.Integer(
        'Máximo períodos acumulables',
        default=1,
        help='1 = un solo período anual “estricto” (bloqueo de nuevo derecho si hay saldo pendiente sin acumulación). '
             '0 u otro valor distinto de 1 = las asignaciones pueden marcarse para acumulación/apilado según la lógica '
             'del sistema (0 no significa “sin acumulación”).',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
    )
    active = fields.Boolean('Activo', default=True)
    notes = fields.Html('Notas')

    _code_company_uniq = models.Constraint(
        'unique(code, company_id)',
        'El código debe ser único por compañía.',
    )

    def get_days_for_seniority(self, years):
        """Retorna los días de vacaciones según años de antigüedad."""
        self.ensure_one()
        if years < 1:
            return 0
        for rule in self.rule_ids.sorted('min_years', reverse=True):
            if rule.min_years <= years and (rule.max_years >= years or rule.max_years >= 99):
                return rule.days_entitled
        return 0
