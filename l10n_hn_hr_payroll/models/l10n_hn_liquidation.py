# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# Liquidación laboral Honduras — CT + Dec. 150-2008.
# Referencia metodológica: https://www.trabajo.gob.hn/wp-content/uploads/2017/11/guiacalculo.pdf

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta


class L10nHnLiquidation(models.Model):
    _name = 'l10n.hn.liquidation'
    _description = 'Labor Liquidation'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'),
    )
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company, tracking=True,
    )

    date = fields.Date(string='Liquidation Date', required=True, default=fields.Date.today, tracking=True)
    reason = fields.Selection([
        ('dismissal', 'Despido (legacy)'),
        ('resignation', 'Renuncia (legacy)'),
        ('natural_death', 'Muerte Natural (legacy)'),
        ('death_outside_work', 'Muerte Fuera de Horario (legacy)'),
    ], string='Reason (legacy)', tracking=False,
        help='Se mapea a Motivo legal. Preferir el campo «Motivo legal».')
    legal_termination_reason = fields.Selection([
        ('resignation', 'Renuncia voluntaria'),
        ('dismissal_unjustified', 'Despido injustificado'),
        ('dismissal_justified', 'Despido justificado'),
        ('death_natural', 'Fallecimiento natural'),
        ('death_accidental_non_occupational', 'Fallecimiento accidental no ocupacional'),
        ('death_occupational', 'Fallecimiento / riesgo profesional (Arts. 417-422)'),
        ('death_pending_legal_classification', 'Fallecimiento — clasificación legal pendiente'),
        ('death_in_itinere', 'Fallecimiento in itinere'),
        ('death_outside_schedule_but_under_employer_order', 'Fuera de horario bajo orden del patrono'),
    ], string='Motivo legal de terminación', required=True, default='resignation', tracking=True)

    death_risk_classification = fields.Selection([
        ('non_occupational', 'No ocupacional'),
        ('in_itinere', 'In itinere'),
        ('employer_order', 'Por orden del empleador'),
        ('occasion_of_work', 'Con ocasión del trabajo'),
        ('occupational_risk_confirmed', 'Riesgo profesional confirmado'),
    ], string='Clasificación riesgo / contexto', tracking=True)

    start_date = fields.Date(string='Start Date', required=True, tracking=True)
    end_date = fields.Date(string='End Date', required=True, tracking=True)

    years_worked = fields.Integer(string='Years Worked', compute='_compute_time_worked', store=True)
    months_worked = fields.Integer(string='Months Worked', compute='_compute_time_worked', store=True)
    days_worked = fields.Integer(string='Days Worked', compute='_compute_time_worked', store=True)

    base_salary = fields.Float(string='Base Salary', digits=(12, 2), compute='_compute_salaries', store=True)
    ordinary_salary = fields.Float(string='Ordinary Salary', digits=(12, 2), compute='_compute_salaries', store=True)
    daily_salary = fields.Float(string='Daily Salary (mensual/30)', digits=(12, 2), compute='_compute_salaries', store=True)

    sbd_computed = fields.Float(string='SBD (calculado)', digits=(12, 4), readonly=True)
    sod_computed = fields.Float(string='SOD (calculado)', digits=(12, 4), readonly=True)
    spd_computed = fields.Float(string='SPD (calculado)', digits=(12, 4), readonly=True)

    current_wage_monthly = fields.Float(
        string='Salario mensual de referencia',
        digits=(12, 2),
        help='Si vacío, se usa la versión contractual actual.',
    )

    input_in_kind_monthly = fields.Monetary(
        string='Salario en especie mensual (Art. 366, tope 30%)',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(related='company_id.currency_id', store=True)

    input_thirteenth_paid_cycle = fields.Monetary(
        string='13° ya pagado en ciclo',
        currency_field='currency_id',
    )
    input_fourteenth_paid_cycle = fields.Monetary(
        string='14° ya pagado en ciclo',
        currency_field='currency_id',
    )
    input_vacation_days_accrued = fields.Float(string='Vacaciones causadas pendientes (días)')
    input_vacation_proportional_days = fields.Float(string='Vacaciones proporcionales (días)')
    input_pending_salary_days = fields.Float(string='Días salario pendiente')
    input_other_pending_income = fields.Monetary(string='Otros ingresos pendientes', currency_field='currency_id')

    input_sbd_manual_override = fields.Float(string='Override SBD (diario)', digits=(12, 4))
    input_sod_manual_override = fields.Float(string='Override SOD (diario)', digits=(12, 4))
    input_spd_manual_override = fields.Float(string='Override SPD (diario)', digits=(12, 4))

    employer_omitted_notice = fields.Boolean(string='Patrono omitió preaviso', default=True)
    employee_renounced_notice = fields.Boolean(string='Trabajador renunció sin preaviso')
    employer_fault_vacation_proportional = fields.Boolean(
        string='Proporcional vacaciones: causa imputable al patrono (Art. 349)',
    )
    force_proportional_vacation_company = fields.Boolean(
        string='Forzar proporcional vacaciones (política — validar legal)',
    )

    occupational_daily_wage = fields.Float(
        string='Salario diario al momento del riesgo (ocupacional)',
        digits=(12, 4),
    )
    ihss_coverage_professional_risk = fields.Boolean(string='Cobertura IHSS riesgo profesional declarada')
    ihss_validation_acknowledged = fields.Boolean(
        string='Validación: no compensar 620 días vs IHSS sin asesoría',
    )
    severance_exclusion_120f_applies = fields.Boolean(string='Exclusión cesantía Art. 120 f) (manual)')
    documents_support_loaded = fields.Boolean(string='Documentación / soporte cargado')

    vacation_eligible_accumulation_art350 = fields.Boolean(
        string='Cargo elegible acumulación vac. (Art. 350)',
        help='Dirección, confianza o análogo; máximo 2 períodos legales.',
    )

    income_ids = fields.One2many('l10n.hn.liquidation.income', 'liquidation_id', string='Incomes')
    deduction_ids = fields.One2many('l10n.hn.liquidation.deduction', 'liquidation_id', string='Deductions')
    beneficiary_ids = fields.One2many('l10n.hn.liquidation.beneficiary', 'liquidation_id', string='Beneficiarios')
    recompute_log_ids = fields.One2many('l10n.hn.liquidation.recompute.log', 'liquidation_id', string='Logs recálculo')

    total_incomes = fields.Float(string='Total Incomes', digits=(12, 2), compute='_compute_totals', store=True)
    total_deductions = fields.Float(string='Total Deductions', digits=(12, 2), compute='_compute_totals', store=True)
    net_amount = fields.Float(string='Net Amount', digits=(12, 2), compute='_compute_totals', store=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('simulated', 'Simulación'),
        ('waiting_approval', 'Waiting Approval'),
        ('approved', 'Approved'),
        ('liquidated', 'Liquidated'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='draft', required=True, tracking=True)

    is_simulation = fields.Boolean(string='Es simulación', default=False)
    calculation_snapshot_json = fields.Text(string='Snapshot cálculo (JSON)', copy=False)
    last_recompute_reason = fields.Text(string='Motivo último recálculo (borrador)')
    requires_legal_review = fields.Boolean(
        string='Requiere revisión legal',
        compute='_compute_requires_legal_review',
        store=True,
    )

    notes = fields.Text(string='Notes')
    legal_reference_note = fields.Text(
        string='Nota fuentes',
        default='Topes cesantía: Decreto 150-2008 (25 meses; 15 micro Art. 120-A). '
                'Guía STSS trabajo.gob.hn solo metodológica si contradicen topes.',
    )

    @api.depends('legal_termination_reason', 'force_proportional_vacation_company', 'ihss_coverage_professional_risk')
    def _compute_requires_legal_review(self):
        for rec in self:
            rev = False
            if rec.force_proportional_vacation_company:
                rev = True
            if rec.legal_termination_reason == 'death_accidental_non_occupational':
                rev = True
            if rec.legal_termination_reason == 'death_pending_legal_classification':
                rev = True
            if rec.ihss_coverage_professional_risk and rec.legal_termination_reason == 'death_occupational':
                rev = True
            rec.requires_legal_review = rev

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('l10n.hn.liquidation') or _('New')
            if vals.get('reason') and not vals.get('legal_termination_reason'):
                vals['legal_termination_reason'] = self._legacy_reason_to_legal_static(vals['reason'])
        return super().create(vals_list)

    @staticmethod
    def _legacy_reason_to_legal_static(reason):
        return {
            'dismissal': 'dismissal_unjustified',
            'resignation': 'resignation',
            'natural_death': 'death_natural',
            'death_outside_work': 'death_accidental_non_occupational',
        }.get(reason, 'resignation')

    def _map_legacy_reason(self):
        self.ensure_one()
        return self._legacy_reason_to_legal_static(self.reason) if self.reason else 'resignation'

    @api.onchange('reason')
    def _onchange_reason_sync_legal(self):
        if self.reason:
            self.legal_termination_reason = self._map_legacy_reason()

    @api.onchange('employee_id')
    def _onchange_employee_dates_wage(self):
        if self.employee_id:
            v = self.employee_id.current_version_id
            if v and v.contract_date_start and not self.start_date:
                self.start_date = v.contract_date_start
            if v and v.wage and not self.current_wage_monthly:
                self.current_wage_monthly = v.wage

    @api.depends('start_date', 'end_date')
    def _compute_time_worked(self):
        for rec in self:
            if rec.start_date and rec.end_date:
                delta = relativedelta(rec.end_date, rec.start_date)
                rec.years_worked = delta.years
                rec.months_worked = delta.months
                rec.days_worked = delta.days
            else:
                rec.years_worked = 0
                rec.months_worked = 0
                rec.days_worked = 0

    @api.depends('employee_id', 'end_date', 'current_wage_monthly')
    def _compute_salaries(self):
        for rec in self:
            base = 0.0
            if rec.current_wage_monthly:
                base = rec.current_wage_monthly
            elif rec.employee_id and rec.employee_id.current_version_id:
                base = rec.employee_id.current_version_id.wage or 0.0
            rec.base_salary = base
            rec.ordinary_salary = base
            rec.daily_salary = base / 30.0 if base else 0.0

    @api.depends('income_ids.amount', 'deduction_ids.amount')
    def _compute_totals(self):
        for rec in self:
            rec.total_incomes = sum(rec.income_ids.mapped('amount'))
            rec.total_deductions = sum(rec.deduction_ids.mapped('amount'))
            rec.net_amount = rec.total_incomes - rec.total_deductions

    def _liquidation_notify(self, title, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message, 'type': 'success', 'sticky': False},
        }

    def action_calculate(self):
        self.ensure_one()
        self.env['hn.liquidation.engine'].apply_to_record(self, simulation=False)
        return self._liquidation_notify(
            _('Liquidación'),
            _('Cálculo completado: %d ingresos, %d deducciones.') % (
                len(self.income_ids), len(self.deduction_ids)),
        )

    def action_simulate_settlement(self):
        self.ensure_one()
        self.env['hn.liquidation.engine'].apply_to_record(self, simulation=True)
        return self._liquidation_notify(
            _('Simulación'),
            _('Simulación generada (estado «Simulación»).'),
        )

    def action_recompute_settlement(self):
        self.ensure_one()
        reason = (self.last_recompute_reason or '').strip()
        if not reason:
            raise UserError(_('Indique el motivo del recálculo en el campo «Motivo último recálculo».'))
        self.env['hn.liquidation.engine'].apply_to_record(
            self, simulation=False, log_reason=reason,
        )
        return self._liquidation_notify(
            _('Recálculo'),
            _('Recálculo registrado. Revise la pestaña Trazabilidad.'),
        )

    def validate_settlement(self):
        self.ensure_one()
        if self.legal_termination_reason in (
            'death_natural',
            'death_occupational',
            'death_accidental_non_occupational',
            'death_pending_legal_classification',
            'death_in_itinere',
            'death_outside_schedule_but_under_employer_order',
        ):
            if not self.beneficiary_ids:
                raise ValidationError(_('Registre al menos un beneficiario / causahabiente.'))
            if not self.documents_support_loaded:
                raise ValidationError(_('Marque «Documentación cargada» o adjunte soporte en el chatter.'))
        if self.legal_termination_reason == 'death_occupational':
            if not self.occupational_daily_wage:
                raise ValidationError(_('Defina el salario diario al momento del riesgo.'))
            if not self.ihss_validation_acknowledged:
                raise UserError(
                    _('Confirme la casilla de validación IHSS / 620 días o consulte asesoría laboral.')
                )
        self.message_post(body=_('Validación RH/Legal superada (revisar advertencias en cabecera).'))

    def action_validate_settlement(self):
        self.ensure_one()
        self.validate_settlement()
        return self._liquidation_notify(_('Validación'), _('Validación completada.'))

    def recompute_after_reclassification(self):
        self.ensure_one()
        self.last_recompute_reason = (_('Reclasificación legal: %s') % (self.death_risk_classification or ''))
        return self.action_recompute_settlement()

    def action_submit_waiting_approval(self):
        self.ensure_one()
        self.validate_settlement()
        self.write({'state': 'waiting_approval', 'is_simulation': False})
        self.message_post(body=_('Enviada a aprobación.'))
        return True

    def action_cancel(self):
        self.ensure_one()
        if self.state == 'liquidated':
            raise UserError(_('No puede cancelar una liquidación ya liquidada.'))
        self.write({'state': 'cancelled'})

    def _hn_engine_apply_loan_deductions(self):
        unpaid = self.env['hr.employee.recurring.concept'].search([
            ('employee_id', '=', self.employee_id.id),
            ('concept_type', '=', 'deduction'),
            ('is_loan', '=', True),
            ('active', '=', True),
        ])
        seq = 800
        for concept in unpaid:
            remaining = concept.remaining_amount or concept.total_amount or 0
            if remaining > 0:
                self.env['l10n.hn.liquidation.deduction'].create({
                    'liquidation_id': self.id,
                    'sequence': seq,
                    'concept': 'accounts_receivable',
                    'concept_code': 'accounts_receivable',
                    'name': concept.name,
                    'amount': remaining,
                    'rule_origin': 'company_policy',
                    'legal_note': _('Préstamo / cuenta por cobrar'),
                })
                seq += 1

    def action_approve(self):
        self.ensure_one()
        if self.state != 'waiting_approval':
            raise UserError(_('Solo se pueden aprobar liquidaciones en espera de aprobación.'))
        self.state = 'approved'
        self.message_post(body=_('Liquidación aprobada.'))

    def action_liquidate(self):
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_('Solo se pueden liquidar liquidaciones aprobadas.'))
        if self.is_simulation:
            raise UserError(_('No liquidar una simulación. Recalcule sin simular.'))
        for income in self.income_ids:
            if income.concept == 'thirteenth_month':
                thirteenth = self.env['l10n.hn.thirteenth.month'].search([
                    ('employee_id', '=', self.employee_id.id),
                    ('year', '=', self.end_date.year),
                ], limit=1)
                if thirteenth:
                    thirteenth.paid = True
            if income.concept == 'fourteenth_month':
                fourteenth = self.env['l10n.hn.fourteenth.month'].search([
                    ('employee_id', '=', self.employee_id.id),
                    ('year', '=', self.end_date.year),
                ], limit=1)
                if fourteenth:
                    fourteenth.paid = True
        self.write({'state': 'liquidated', 'is_simulation': False})
        self.message_post(body=_('Liquidación completada y pagada.'))


INCOME_CONCEPT_SELECTION = [
    ('advance_notice', 'Aviso Previo'),
    ('severance', 'Asistencia de Cesantía'),
    ('proportional_severance', 'Asistencia Proporcional de Cesantía'),
    ('accrued_vacation', 'Vacaciones Causadas'),
    ('proportional_vacation', 'Vacaciones Proporcionales'),
    ('thirteenth_month', 'Décimo Tercer Mes'),
    ('proportional_thirteenth', 'Décimo Tercer Mes Proporcional'),
    ('fourteenth_month', 'Décimo Cuarto Mes'),
    ('proportional_fourteenth', 'Décimo Cuarto Mes Proporcional'),
    ('vacation_bonus', 'Bono Proporcional de Vacaciones'),
    ('pending_days', 'Pago de Días Trabajados Pendientes'),
    ('labor_reserve', 'Reserva Laboral'),
    ('lactation_hours', 'Pagos de Horas de Lactancia'),
    ('overtime', 'Horas Extras'),
    ('occupational_funeral', 'Indemnización — mes fúnebres (riesgo profesional)'),
    ('occupational_620', 'Indemnización — 620 días (riesgo profesional)'),
    ('other', 'Otros Ingresos'),
]

DEDUCTION_CONCEPT_SELECTION = [
    ('advance_notice_deduction', '50% Anticipo de Aviso'),
    ('accounts_receivable', 'Cuentas por Cobrar'),
    ('loan_hsj', 'Préstamos HSJ'),
    ('loan_rap', 'Préstamos RAP'),
    ('cooperative', 'Cooperativa'),
    ('optics', 'Óptica Santa Lucía'),
    ('advance_vacation', 'Vacaciones Tomadas por Adelantado'),
    ('reserve_adjustment', 'Reajuste Reserva Laboral'),
    ('other', 'Otras Deducciones'),
]

SALARY_BASE_SELECTION = [
    ('none', 'N/A'),
    ('sbd', 'SBD — salario base diario'),
    ('sod', 'SOD — salario ordinario diario'),
    ('spd', 'SPD — salario promedio diario'),
    ('occupational_daily', 'Salario diario riesgo profesional'),
]

RULE_ORIGIN_SELECTION = [
    ('labor_rule', 'Norma laboral obligatoria'),
    ('company_policy', 'Política empresa / validación'),
]

PAYEE_SELECTION = [
    ('employee', 'Trabajador'),
    ('beneficiary', 'Beneficiario / causahabiente'),
]


class L10nHnLiquidationIncome(models.Model):
    _name = 'l10n.hn.liquidation.income'
    _description = 'Liquidation Income Line'
    _order = 'sequence, id'

    liquidation_id = fields.Many2one('l10n.hn.liquidation', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    concept = fields.Selection(INCOME_CONCEPT_SELECTION, required=True)
    concept_code = fields.Char(string='Código concepto')
    name = fields.Char(string='Description', required=True)
    amount = fields.Float(string='Amount', digits=(12, 2), required=True)
    salary_base_used = fields.Selection(SALARY_BASE_SELECTION, string='Base salarial', default='none')
    quantity_days = fields.Float(string='Días', digits=(12, 4))
    quantity_hours = fields.Float(string='Horas', digits=(12, 4))
    payee_type = fields.Selection(PAYEE_SELECTION, string='Paga a', default='employee')
    legal_note = fields.Text(string='Referencia legal / trazabilidad')
    rule_origin = fields.Selection(RULE_ORIGIN_SELECTION, string='Origen regla', default='labor_rule')

    def _hn_liquidation_line_edit_guard(self):
        if self.env.context.get('hn_liquidation_engine_recompute'):
            return
        for line in self:
            if line.liquidation_id.state in ('approved', 'liquidated'):
                if not self.env.user.has_group(
                    'l10n_hn_hr_payroll.group_hn_liquidation_adjust_confirmed'
                ):
                    raise UserError(_('Liquidación aprobada o liquidada: no puede editar líneas sin permiso.'))

    def write(self, vals):
        self._hn_liquidation_line_edit_guard()
        return super().write(vals)

    def unlink(self):
        self._hn_liquidation_line_edit_guard()
        return super().unlink()


class L10nHnLiquidationDeduction(models.Model):
    _name = 'l10n.hn.liquidation.deduction'
    _description = 'Liquidation Deduction Line'
    _order = 'sequence, id'

    liquidation_id = fields.Many2one('l10n.hn.liquidation', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    concept = fields.Selection(DEDUCTION_CONCEPT_SELECTION, required=True)
    concept_code = fields.Char(string='Código concepto')
    name = fields.Char(string='Description', required=True)
    amount = fields.Float(string='Amount', digits=(12, 2), required=True)
    salary_base_used = fields.Selection(SALARY_BASE_SELECTION, string='Base salarial', default='none')
    quantity_days = fields.Float(string='Días', digits=(12, 4))
    legal_note = fields.Text(string='Referencia legal / trazabilidad')
    rule_origin = fields.Selection(RULE_ORIGIN_SELECTION, string='Origen regla', default='labor_rule')

    def _hn_liquidation_line_edit_guard(self):
        if self.env.context.get('hn_liquidation_engine_recompute'):
            return
        for line in self:
            if line.liquidation_id.state in ('approved', 'liquidated'):
                if not self.env.user.has_group(
                    'l10n_hn_hr_payroll.group_hn_liquidation_adjust_confirmed'
                ):
                    raise UserError(_('Liquidación aprobada o liquidada: no puede editar líneas sin permiso.'))

    def write(self, vals):
        self._hn_liquidation_line_edit_guard()
        return super().write(vals)

    def unlink(self):
        self._hn_liquidation_line_edit_guard()
        return super().unlink()
