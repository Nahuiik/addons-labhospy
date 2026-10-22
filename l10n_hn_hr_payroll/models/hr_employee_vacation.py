# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

from calendar import monthrange
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    hn_vacation_plan_id = fields.Many2one(
        'gn.hn.vacation.plan',
        string='Plan de Vacaciones',
        help='Plan de vacaciones asignado. Si está vacío, se usa el plan por defecto de la compañía.',
    )
    hn_is_temporary = fields.Boolean(
        'Es temporal',
        default=False,
        help='Empleado temporal/eventual. Se deduce de contract_date_end si está definido.',
    )
    hn_vacation_requests_allowed = fields.Boolean(
        string='Puede solicitar vacaciones (portal)',
        default=True,
        help='Solo afecta al portal del empleado: si está desmarcado, no podrá elegir ni enviar solicitudes del '
             'tipo de ausencia principal de vacaciones Honduras (gn_vacation_is_primary) desde el portal; el resumen '
             'y el formulario siguen mostrando otros tipos de ausencia. '
             'En el backend (Time Off, vacaciones masivas, etc.) no aplica esta restricción.',
    )
    hn_override_anniversary_vacation_block = fields.Boolean(
        string='Excepción: vacaciones antes del aniversario',
        default=False,
        help='Si el tipo de ausencia de vacaciones HN tiene activa la regla de no solicitar antes del '
             'aniversario laboral, marcar aquí permite a este empleado saltar esa regla (portal y validaciones '
             'automáticas). Los usuarios con permiso de Ausencias/RRHH no están sujetos a la regla en el backend.',
    )
    hn_initial_vacation_taken = fields.Float(
        'Saldo inicial de vacaciones',
        help='Días de vacaciones ya gozados antes de implementar el módulo (carga inicial). '
             'Es 0 cuando el tipo de contrato no es permanente.',
    )
    hn_initial_vacation_taken_display = fields.Float(
        string='Saldo inicial (mostrado)',
        compute='_compute_hn_initial_vacation_taken_display',
        help='Muestra 0 cuando contract_type_id tiene permanente=False',
    )

    @api.depends('hn_initial_vacation_taken', 'contract_type_id')
    def _compute_hn_initial_vacation_taken_display(self):
        for emp in self:
            if emp.contract_type_id and not getattr(emp.contract_type_id, 'is_permanent', True):
                emp.hn_initial_vacation_taken_display = 0.0
            else:
                emp.hn_initial_vacation_taken_display = emp.hn_initial_vacation_taken or 0.0
    hn_initial_balance_date = fields.Date('Fecha de corte saldo inicial')
    hn_initial_balance_loaded = fields.Boolean('Saldo inicial cargado', default=False)

    # Campos computed para el tab de vacaciones
    hn_seniority_years = fields.Integer(
        string='Antigüedad (años)',
        compute='_compute_hn_seniority',
    )
    hn_seniority_display = fields.Char(
        string='Antigüedad',
        compute='_compute_hn_seniority',
        help='Antigüedad en años, meses y días (ej: 1 año 10 meses y 5 días)',
    )
    hn_current_entitled_days = fields.Float(
        string='Días que le corresponden',
        compute='_compute_hn_vacation_data',
        help='Suma de días en asignaciones de vacaciones HN validadas (según lo generado por el plan: anual, '
             'mensual o diario). Sin asignaciones es 0.',
    )
    hn_current_balance = fields.Float(
        string='Saldo actual',
        compute='_compute_hn_vacation_data',
        help='Suma de (días otorgados − tomados) por asignaciones HN validadas, menos el saldo inicial cargado '
        'cuando aplica. Es el saldo de tiempo libre; no es el importe ni los días de liquidación de la nómina '
        'de vacaciones HN.',
    )
    hn_vacation_balance = fields.Float(
        string='Saldo de vacaciones',
        compute='_compute_hn_vacation_data',
        help='Días otorgados en asignaciones (ver «Días que le corresponden») − saldo inicial mostrado − días de '
             'ausencias HN validadas. Se recalcula al cambiar o eliminar asignaciones o solicitudes.',
    )
    hn_vacation_allocation_ids = fields.One2many(
        'hr.leave.allocation',
        'employee_id',
        string='Asignaciones HN',
        help='Historial de asignaciones de vacaciones Honduras',
    )
    hn_vacation_leave_ids = fields.One2many(
        'hr.leave',
        'employee_id',
        string='Vacaciones HN',
        help='Historial de solicitudes de vacaciones Honduras',
    )

    def write(self, vals):
        """Si contract_type_id tiene permanente=False, hn_initial_vacation_taken debe ser 0.
        is_permanent viene de l10n_hn_hr_payroll; si no está instalado, getattr(..., True) asume permanente.
        """
        vals = dict(vals)
        if 'contract_type_id' in vals and vals.get('contract_type_id'):
            ct = self.env['hr.contract.type'].browse(vals['contract_type_id'])
            if ct and not getattr(ct, 'is_permanent', True):
                vals['hn_initial_vacation_taken'] = 0.0
        if 'hn_initial_vacation_taken' in vals:
            non_permanent = self.filtered(
                lambda e: e.contract_type_id and not getattr(e.contract_type_id, 'is_permanent', True)
            )
            if non_permanent:
                super(HrEmployee, non_permanent).write(dict(vals, hn_initial_vacation_taken=0.0))
                rest = self - non_permanent
                return super(HrEmployee, rest).write(vals) if rest else True
        return super().write(vals)

    def _hn_primary_vacation_leave_type(self):
        """Tipo principal de vacaciones para la compañía del empleado (país + alcance compañía)."""
        self.ensure_one()
        company = self.company_id or self.env.company
        return self.env["hr.leave.type"].gn_primary_vacation_leave_type(company)

    @api.depends('contract_date_start')
    def _compute_hn_seniority(self):
        today = date.today()
        for emp in self:
            if emp.contract_date_start:
                delta = relativedelta(today, emp.contract_date_start)
                emp.hn_seniority_years = delta.years
                parts = []
                if delta.years:
                    parts.append(f'{delta.years} año{"s" if delta.years != 1 else ""}')
                if delta.months:
                    parts.append(f'{delta.months} mes{"es" if delta.months != 1 else ""}')
                if delta.days:
                    parts.append(f'{delta.days} día{"s" if delta.days != 1 else ""}')
                emp.hn_seniority_display = ' '.join(parts) if parts else '0 días'
            else:
                emp.hn_seniority_years = 0
                emp.hn_seniority_display = ''

    @api.depends(
        'hn_vacation_plan_id', 'hn_vacation_plan_id.vacation_accrual_mode',
        'hn_vacation_plan_id.vacation_year_basis',
        'hn_vacation_plan_id.vacation_allocation_scope',
        'hn_vacation_plan_id.max_accumulation_periods',
        'hn_seniority_years', 'contract_date_start',
        'company_id', 'company_id.country_id',
        'hn_initial_vacation_taken', 'hn_initial_balance_loaded',
        'contract_type_id',
        'hn_vacation_allocation_ids',
        'hn_vacation_allocation_ids.number_of_days',
        'hn_vacation_allocation_ids.leaves_taken',
        'hn_vacation_allocation_ids.state',
        'hn_vacation_leave_ids',
        'hn_vacation_leave_ids.number_of_days',
        'hn_vacation_leave_ids.state',
    )
    def _compute_hn_vacation_data(self):
        today = date.today()
        emp_ids = self.filtered('id').ids
        LeaveType = self.env['hr.leave.type']
        primary_lt_by_emp = {}
        for eid in emp_ids:
            emp = self.env['hr.employee'].browse(eid)
            lt = LeaveType.gn_primary_vacation_leave_type(emp.company_id or self.env.company)
            primary_lt_by_emp[eid] = lt.id if lt else None

        all_allocations = self.env['hr.leave.allocation'].search([
            ('employee_id', 'in', emp_ids),
            ('state', '=', 'validate'),
            ('holiday_status_id.gn_vacation_is_primary', '=', True),
        ]) if emp_ids else self.env['hr.leave.allocation']
        all_allocations = all_allocations.filtered(
            lambda a: primary_lt_by_emp.get(a.employee_id.id) == a.holiday_status_id.id
        )
        all_leaves = self.env['hr.leave'].search([
            ('employee_id', 'in', emp_ids),
            ('holiday_status_id.gn_vacation_is_primary', '=', True),
            ('state', 'in', ('validate', 'validate1')),
        ]) if emp_ids else self.env['hr.leave']
        all_leaves = all_leaves.filtered(
            lambda lv: primary_lt_by_emp.get(lv.employee_id.id) == lv.holiday_status_id.id
        )

        allocations_by_emp = {eid: self.env['hr.leave.allocation'] for eid in emp_ids}
        for alloc in all_allocations:
            allocations_by_emp[alloc.employee_id.id] |= alloc
        leaves_by_emp = {eid: self.env['hr.leave'] for eid in emp_ids}
        for lv in all_leaves:
            leaves_by_emp[lv.employee_id.id] |= lv

        for emp in self:
            allocations = allocations_by_emp.get(emp.id, self.env['hr.leave.allocation'])
            leaves = leaves_by_emp.get(emp.id, self.env['hr.leave'])

            # Días otorgados por asignaciones validadas (refleja borrados/altas de asignaciones)
            entitled_sum = sum(alloc.number_of_days or 0.0 for alloc in allocations)
            emp.hn_current_entitled_days = entitled_sum

            balance = 0.0
            for alloc in allocations:
                balance += (alloc.number_of_days or 0.0) - (alloc.leaves_taken or 0.0)

            initial_taken = 0.0
            if not (emp.contract_type_id and not getattr(emp.contract_type_id, 'is_permanent', True)):
                initial_taken = emp.hn_initial_vacation_taken or 0
            emp.hn_current_balance = balance - initial_taken

            total_taken = sum(lv.number_of_days or 0.0 for lv in leaves)
            emp.hn_vacation_balance = (
                emp.hn_current_entitled_days - emp.hn_initial_vacation_taken_display - total_taken
            )

    def action_open_hn_initial_balance_wizard(self):
        """Abre el wizard de cargar saldo inicial con este empleado preseleccionado."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Cargar saldo inicial de vacaciones',
            'res_model': 'hn.initial.balance.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_balance_date': date.today(),
                'active_model': 'hr.employee',
                'active_ids': [self.id],
            },
        }

    def _hn_last_anniversary(self, ref_date=None):
        """Calcula la fecha del último aniversario laboral del empleado."""
        self.ensure_one()
        ref_date = ref_date or date.today()
        start = self.contract_date_start
        if not start:
            return False
        try:
            anniversary_this_year = start.replace(year=ref_date.year)
        except ValueError:
            anniversary_this_year = start.replace(year=ref_date.year, day=28)
        if anniversary_this_year > ref_date:
            try:
                return start.replace(year=ref_date.year - 1)
            except ValueError:
                return start.replace(year=ref_date.year - 1, day=28)
        return anniversary_this_year

    def _hn_current_labor_year_bounds(self, ref_date):
        """Inicio y fin (inclusive) del año laboral vigente en ref_date, anclado a contract_date_start."""
        self.ensure_one()
        start = self.contract_date_start
        if not start or ref_date < start:
            return False, False
        if relativedelta(ref_date, start).years < 1:
            period_start = start
            period_end = start + relativedelta(years=1) - relativedelta(days=1)
        else:
            period_start = self._hn_last_anniversary(ref_date)
            period_end = period_start + relativedelta(years=1) - relativedelta(days=1)
        return period_start, period_end

    def _hn_current_period_bounds_for_plan(self, hire, ref_date, plan):
        """Período vacacional vigente según el plan: año laboral o año calendario."""
        if not hire or not ref_date or ref_date < hire:
            return False, False
        basis = getattr(plan, 'vacation_year_basis', 'labor') or 'labor'
        if basis == 'civil':
            y = ref_date.year
            period_start = max(hire, date(y, 1, 1))
            period_end = date(y, 12, 31)
            if ref_date < period_start:
                return False, False
            return period_start, period_end
        return self._hn_current_labor_year_bounds(ref_date)

    def _hn_period_days_entitled(self, plan, hire, period_start, period_end):
        """Días anuales de tabla (D) para el período según base laboral o civil."""
        basis = getattr(plan, 'vacation_year_basis', 'labor') or 'labor'
        if basis == 'civil':
            ey = max(1, relativedelta(period_end, hire).years + 1)
            return plan.get_days_for_seniority(ey)
        k = relativedelta(period_start, hire).years
        return plan.get_days_for_seniority(k + 1)

    def _hn_iter_vacation_periods(self, hire, until, plan):
        """Itera períodos (k, inicio, fin) hasta until; base año laboral o año civil."""
        basis = getattr(plan, 'vacation_year_basis', 'labor') or 'labor'
        if basis == 'civil':
            y = hire.year
            while True:
                period_end = date(y, 12, 31)
                period_start = max(hire, date(y, 1, 1))
                if period_start > until or period_start > period_end:
                    break
                k = y - hire.year
                yield k, period_start, period_end
                y += 1
            return
        k = 0
        while True:
            period_start = hire + relativedelta(years=k)
            if period_start > until:
                break
            period_end = period_start + relativedelta(years=1) - relativedelta(days=1)
            yield k, period_start, period_end
            k += 1

    def _hn_iter_vacation_periods_for_sync(self, hire, until, plan):
        """Igual que _hn_iter_vacation_periods, pero si el plan pide solo período vigente, una sola tupla."""
        scope = getattr(plan, 'vacation_allocation_scope', 'all') or 'all'
        if scope != 'current':
            yield from self._hn_iter_vacation_periods(hire, until, plan)
            return
        cps, cpe = self._hn_current_period_bounds_for_plan(hire, until, plan)
        if not cps:
            return
        matched = False
        for k, ps, pe in self._hn_iter_vacation_periods(hire, until, plan):
            if ps == cps and pe == cpe:
                yield k, ps, pe
                matched = True
        if not matched:
            basis = getattr(plan, 'vacation_year_basis', 'labor') or 'labor'
            k = (cps.year - hire.year) if basis == 'civil' else relativedelta(cps, hire).years
            yield k, cps, cpe

    def _hn_iter_contract_labor_periods(self, hire: date, until: date):
        """Compat: año laboral sin plan (solo usos legacy internos)."""
        k = 0
        while True:
            period_start = hire + relativedelta(years=k)
            if period_start > until:
                break
            period_end = period_start + relativedelta(years=1) - relativedelta(days=1)
            yield k, period_start, period_end
            k += 1

    def _hn_monthly_target_days_in_period(self, period_start: date, period_end: date, ref_date: date, days_full: float):
        """Días devengados con regla mensual dentro del período; D ya resuelto en la tabla del plan."""
        if days_full <= 0:
            return 0.0
        if ref_date > period_end:
            return float(days_full)
        ref = min(ref_date, period_end)
        months_elapsed = (ref.year - period_start.year) * 12 + ref.month - period_start.month
        if ref.day < period_start.day:
            months_elapsed -= 1
        months_elapsed = max(0, min(12, months_elapsed))
        return round((months_elapsed / 12.0) * float(days_full), 4)

    def _hn_daily_target_days_in_period(self, period_start: date, period_end: date, ref_date: date, days_full: float):
        """Días devengados con regla diaria dentro del período (duración natural del intervalo)."""
        if days_full <= 0:
            return 0.0
        if ref_date > period_end:
            return float(days_full)
        period_len = (period_end - period_start).days + 1
        if period_len <= 0:
            return 0.0
        end_acc = min(ref_date, period_end)
        days_elapsed = (end_acc - period_start).days + 1
        days_elapsed = max(0, min(period_len, days_elapsed))
        return round(days_elapsed / float(period_len) * float(days_full), 4)

    @staticmethod
    def _hn_plan_allows_allocation_stack(plan):
        """Solo max=1 fuerza un único período anual sin facilidad de apilar; 0 u ≥2 permiten más de uno."""
        return plan.max_accumulation_periods != 1

    def _hn_sync_annual_allocations(self, plan, vacation_type, today):
        """Modo anual: asignaciones completas por período (año laboral o año civil según plan)."""
        self.ensure_one()
        LeaveAllocation = self.env['hr.leave.allocation']
        result = {'names': [], 'created_current': False, 'blocked_current_by_pending': False, 'pending_remaining': 0.0}
        start = self.contract_date_start
        if not start or plan.vacation_accrual_mode != 'annual':
            return result
        basis = getattr(plan, 'vacation_year_basis', 'labor') or 'labor'
        if basis == 'civil':
            return self._hn_sync_annual_allocations_civil(plan, vacation_type, today, LeaveAllocation, result)
        years_now = relativedelta(today, start).years
        if years_now < 1:
            return result
        first_anniversary = start + relativedelta(years=1)
        if today < first_anniversary:
            return result
        last_a = self._hn_last_anniversary(today)
        allow_stack = self._hn_plan_allows_allocation_stack(plan)
        scope = getattr(plan, 'vacation_allocation_scope', 'all') or 'all'
        if scope == 'current':
            m = relativedelta(last_a, start).years
            if m < 1:
                return result
            period_start = last_a
            period_end = last_a + relativedelta(years=1) - relativedelta(days=1)
            period_specs = [(m, period_start, period_end)]
        else:
            period_specs = []
            for m in range(1, years_now + 2):
                p_start = start + relativedelta(years=m)
                if p_start > today:
                    break
                p_end = start + relativedelta(years=m + 1) - relativedelta(days=1)
                is_open_current = p_start == last_a
                if p_end > today and not is_open_current:
                    continue
                period_specs.append((m, p_start, p_end))
        for m, period_start, period_end in period_specs:
            is_open_current = period_start == last_a
            if period_end > today and not is_open_current:
                continue
            days = plan.get_days_for_seniority(m)
            if days <= 0:
                continue
            existing = LeaveAllocation.search([
                ('employee_id', '=', self.id),
                ('holiday_status_id', '=', vacation_type.id),
                ('state', '=', 'validate'),
                ('hn_is_monthly_proportional', '=', False),
                ('hn_vacation_period_start', '=', period_start),
            ], limit=1)
            if existing:
                continue
            if is_open_current:
                pending = LeaveAllocation.search([
                    ('employee_id', '=', self.id),
                    ('holiday_status_id', '=', vacation_type.id),
                    ('state', '=', 'validate'),
                    ('hn_is_monthly_proportional', '=', False),
                ])
                remaining = sum(
                    (a.number_of_days or 0.0) - (a.leaves_taken or 0.0) for a in pending
                )
                if remaining > 0 and not any(a.hn_allow_accumulation for a in pending):
                    result['blocked_current_by_pending'] = True
                    result['pending_remaining'] = remaining
                    continue
            alloc = LeaveAllocation.sudo().create({
                'name': f'Vacaciones {m} año(s) laborales - {period_start.year}',
                'employee_id': self.id,
                'holiday_status_id': vacation_type.id,
                'number_of_days': days,
                'date_from': period_start,
                'date_to': period_end,
                'hn_vacation_period_start': period_start,
                'hn_vacation_period_end': period_end,
                'hn_allow_accumulation': allow_stack,
            })
            if alloc.state == 'confirm':
                alloc.sudo().action_approve()
            result['names'].append(alloc.name)
            if is_open_current:
                result['created_current'] = True
        return result

    def _hn_sync_annual_allocations_civil(self, plan, vacation_type, today, LeaveAllocation, result):
        """Anual con períodos 1 ene – 31 dic; cupo completo por año civil."""
        self.ensure_one()
        start = self.contract_date_start
        allow_stack = self._hn_plan_allows_allocation_stack(plan)
        scope = getattr(plan, 'vacation_allocation_scope', 'all') or 'all'
        year_lo = today.year if scope == 'current' else start.year
        year_hi = today.year
        for y in range(year_lo, year_hi + 1):
            period_end = date(y, 12, 31)
            period_start = max(start, date(y, 1, 1))
            if period_start > today or period_start > period_end:
                continue
            is_open_current = y == today.year
            if period_end > today and not is_open_current:
                continue
            days = self._hn_period_days_entitled(plan, start, period_start, period_end)
            if days <= 0:
                continue
            existing = LeaveAllocation.search([
                ('employee_id', '=', self.id),
                ('holiday_status_id', '=', vacation_type.id),
                ('state', '=', 'validate'),
                ('hn_is_monthly_proportional', '=', False),
                ('hn_vacation_period_start', '=', period_start),
            ], limit=1)
            if existing:
                continue
            if is_open_current:
                pending = LeaveAllocation.search([
                    ('employee_id', '=', self.id),
                    ('holiday_status_id', '=', vacation_type.id),
                    ('state', '=', 'validate'),
                    ('hn_is_monthly_proportional', '=', False),
                ])
                remaining = sum(
                    (a.number_of_days or 0.0) - (a.leaves_taken or 0.0) for a in pending
                )
                if remaining > 0 and not any(a.hn_allow_accumulation for a in pending):
                    result['blocked_current_by_pending'] = True
                    result['pending_remaining'] = remaining
                    continue
            alloc = LeaveAllocation.sudo().create({
                'name': f'Vacaciones año civil {y}',
                'employee_id': self.id,
                'holiday_status_id': vacation_type.id,
                'number_of_days': days,
                'date_from': period_start,
                'date_to': period_end,
                'hn_vacation_period_start': period_start,
                'hn_vacation_period_end': period_end,
                'hn_allow_accumulation': allow_stack,
            })
            if alloc.state == 'confirm':
                alloc.sudo().action_approve()
            result['names'].append(alloc.name)
            if is_open_current:
                result['created_current'] = True
        return result

    def _hn_refuse_first_year_proportional_allocations(self, vacation_type, hire_start):
        """Al pasar a asignaciones anuales, cierra el bloque proporcional del primer año (misma fecha de inicio que el ingreso)."""
        LeaveAllocation = self.env['hr.leave.allocation']
        to_refuse = LeaveAllocation.search([
            ('employee_id', '=', self.id),
            ('holiday_status_id', '=', vacation_type.id),
            ('hn_is_monthly_proportional', '=', True),
            ('state', '=', 'validate'),
            ('hn_vacation_period_start', '=', hire_start),
        ])
        for m in to_refuse:
            m.sudo().action_refuse()

    def _hn_sync_monthly_year_allocations(self, plan, vacation_type, today):
        """Mensual: una asignación validada por año laboral desde el ingreso; los días suben cada mes en esa fila."""
        self.ensure_one()
        if plan.vacation_accrual_mode != 'monthly':
            return []
        start = self.contract_date_start
        if not start or today < start:
            return []
        LeaveAllocation = self.env['hr.leave.allocation']
        allow_stack = self._hn_plan_allows_allocation_stack(plan)
        out = []
        for k, period_start, period_end in self._hn_iter_vacation_periods_for_sync(start, today, plan):
            days_full = float(self._hn_period_days_entitled(plan, start, period_start, period_end))
            target = self._hn_monthly_target_days_in_period(period_start, period_end, today, days_full)
            if target <= 0:
                continue
            existing = LeaveAllocation.search([
                ('employee_id', '=', self.id),
                ('holiday_status_id', '=', vacation_type.id),
                ('state', '=', 'validate'),
                ('hn_vacation_period_start', '=', period_start),
            ], limit=1)
            base_name = _('Vacaciones devengo mensual (%(y0)s–%(y1)s)') % {
                'y0': period_start.year,
                'y1': period_end.year,
            }
            vals = {
                'name': base_name,
                'number_of_days': target,
                'date_from': period_start,
                'date_to': period_end,
                'hn_vacation_period_start': period_start,
                'hn_vacation_period_end': period_end,
                'hn_allow_accumulation': allow_stack,
                'hn_is_monthly_proportional': False,
            }
            if existing:
                existing.write(vals)
                out.append(f'Actualizado: {existing.name}')
            else:
                alloc = LeaveAllocation.sudo().create({
                    **vals,
                    'employee_id': self.id,
                    'holiday_status_id': vacation_type.id,
                })
                if alloc.state == 'confirm':
                    alloc.sudo().action_approve()
                out.append(alloc.name)
        return out

    def _hn_sync_daily_year_allocations(self, plan, vacation_type, today):
        """Diario: una asignación por año laboral desde el ingreso; los días suben cada día en esa fila."""
        self.ensure_one()
        if plan.vacation_accrual_mode != 'daily':
            return []
        start = self.contract_date_start
        if not start or today < start:
            return []
        LeaveAllocation = self.env['hr.leave.allocation']
        allow_stack = self._hn_plan_allows_allocation_stack(plan)
        out = []
        for k, period_start, period_end in self._hn_iter_vacation_periods_for_sync(start, today, plan):
            days_full = float(self._hn_period_days_entitled(plan, start, period_start, period_end))
            target = self._hn_daily_target_days_in_period(period_start, period_end, today, days_full)
            if target <= 0:
                continue
            existing = LeaveAllocation.search([
                ('employee_id', '=', self.id),
                ('holiday_status_id', '=', vacation_type.id),
                ('state', '=', 'validate'),
                ('hn_vacation_period_start', '=', period_start),
            ], limit=1)
            base_name = _('Vacaciones devengo diario (%(y0)s–%(y1)s)') % {
                'y0': period_start.year,
                'y1': period_end.year,
            }
            vals = {
                'name': base_name,
                'number_of_days': target,
                'date_from': period_start,
                'date_to': period_end,
                'hn_vacation_period_start': period_start,
                'hn_vacation_period_end': period_end,
                'hn_allow_accumulation': allow_stack,
                'hn_is_monthly_proportional': False,
            }
            if existing:
                existing.write(vals)
                out.append(f'Actualizado: {existing.name}')
            else:
                alloc = LeaveAllocation.sudo().create({
                    **vals,
                    'employee_id': self.id,
                    'holiday_status_id': vacation_type.id,
                })
                if alloc.state == 'confirm':
                    alloc.sudo().action_approve()
                out.append(alloc.name)
        return out

    def _hn_accrual_proportional_days(self, plan, ref_date):
        """Días devengados en el período (laboral o civil) que contiene ref_date; ver _hn_vacation_devengados_at para el total."""
        self.ensure_one()
        if plan.vacation_accrual_mode not in ('monthly', 'daily'):
            return 0.0
        if not self.contract_date_start or ref_date < self.contract_date_start:
            return 0.0
        hire = self.contract_date_start
        period_start, period_end = self._hn_current_period_bounds_for_plan(hire, ref_date, plan)
        if not period_start:
            return 0.0
        days_full = float(self._hn_period_days_entitled(plan, hire, period_start, period_end))
        if plan.vacation_accrual_mode == 'monthly':
            return self._hn_monthly_target_days_in_period(period_start, period_end, ref_date, days_full)
        return self._hn_daily_target_days_in_period(period_start, period_end, ref_date, days_full)

    def _hn_min_vacation_start_for_anniversary_rule(self, request_start):
        """Fecha mínima de inicio si aplica la regla de aniversario; None si la fecha cumple."""
        self.ensure_one()
        hire = self.contract_date_start
        if not hire or not request_start:
            return None
        first_complete = hire + relativedelta(years=1)
        if request_start < first_complete:
            return first_complete
        try:
            ann_this_year = hire.replace(year=request_start.year)
        except ValueError:
            ann_this_year = hire.replace(year=request_start.year, day=28)
        if request_start < ann_this_year:
            return ann_this_year
        return None

    def action_hn_generate_vacation_allocation(self):
        """Genera asignaciones de vacaciones HN para este empleado (igual que el cron, pero manual).
        No requiere que hoy sea la fecha exacta del aniversario."""
        self.ensure_one()
        today = date.today()
        LeaveAllocation = self.env['hr.leave.allocation']
        vacation_type = self._hn_primary_vacation_leave_type()
        if not vacation_type:
            raise UserError(_(
                'No existe tipo de ausencia principal de vacaciones configurado para el país '
                'de la compañía del empleado (marque uno como principal en Tipos de ausencias '
                'y asigne país/compañía).'
            ))

        if not self.contract_date_start:
            raise UserError(_('El empleado no tiene fecha de inicio de contrato.'))

        plan = self.hn_vacation_plan_id or self._get_default_hn_vacation_plan()
        if not plan:
            raise UserError(_('El empleado no tiene plan de vacaciones asignado.'))

        created = []

        # 1) Temporal que termina hoy: asignación proporcional
        if self.contract_date_start and self.contract_date_end and self.contract_date_end == today:
            if plan.allow_proportional:
                days_worked = (self.contract_date_end - self.contract_date_start).days
                if days_worked < 360:
                    days_year1 = plan.get_days_for_seniority(1)
                    if days_year1 > 0:
                        proportional_days = round((days_worked / 360.0) * days_year1, 1)
                        if proportional_days > 0:
                            pending = LeaveAllocation.search([
                                ('employee_id', '=', self.id),
                                ('holiday_status_id', '=', vacation_type.id),
                                ('state', '=', 'validate'),
                            ])
                            if not pending:
                                period_end = today + relativedelta(months=3)
                                alloc = LeaveAllocation.sudo().create({
                                    'name': f'Vacaciones proporcionales temporal - {today.year}',
                                    'employee_id': self.id,
                                    'holiday_status_id': vacation_type.id,
                                    'number_of_days': proportional_days,
                                    'date_from': today,
                                    'date_to': period_end,
                                    'hn_vacation_period_start': self.contract_date_start,
                                    'hn_vacation_period_end': today,
                                    'hn_allow_accumulation': self._hn_plan_allows_allocation_stack(plan),
                                })
                                if alloc.state == 'confirm':
                                    alloc.sudo().action_approve()
                                created.append(alloc.name)

        start = self.contract_date_start
        accrual_mode = plan.vacation_accrual_mode

        if accrual_mode == 'monthly':
            created.extend(self._hn_sync_monthly_year_allocations(plan, vacation_type, today))
        elif accrual_mode == 'daily':
            created.extend(self._hn_sync_daily_year_allocations(plan, vacation_type, today))
        elif accrual_mode == 'annual':
            if (self.hn_is_temporary or self.contract_date_end) and not self.hn_vacation_plan_id:
                plan = self.env['gn.hn.vacation.plan'].search([
                    ('company_id', 'in', [False, (self.company_id or self.env.company).id]),
                    ('is_temporary', '=', True),
                    ('active', '=', True),
                ], limit=1) or plan
            sync = self._hn_sync_annual_allocations(plan, vacation_type, today)
            created.extend(sync['names'])
            if sync['names']:
                self._hn_refuse_first_year_proportional_allocations(vacation_type, start)
            if sync.get('blocked_current_by_pending'):
                remaining = sync.get('pending_remaining', 0.0)
                self.activity_schedule(
                    'l10n_hn_hr_payroll.mail_activity_hn_program_vacation',
                    date_deadline=today + relativedelta(months=3),
                    note=f'Vacaciones pendientes ({remaining:.1f} días). Regularizar antes de generar nuevo período.',
                )
            elif sync.get('created_current'):
                self.activity_schedule(
                    'l10n_hn_hr_payroll.mail_activity_hn_program_vacation',
                    date_deadline=today + relativedelta(months=3),
                    note=f'Definir época de vacaciones antes del {today + relativedelta(months=3)}.',
                )

        if created:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Asignaciones generadas',
                    'message': f'Se crearon/actualizaron: {", ".join(created)}',
                    'type': 'success',
                    'sticky': False,
                },
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sin asignaciones',
                'message': 'No se generó ninguna asignación. Verifique que el empleado tenga contrato, plan de vacaciones y antigüedad suficiente.',
                'type': 'warning',
                'sticky': False,
            },
        }

    @api.model
    def _cron_hn_vacation_annual_allocation(self):
        """Cron diario: genera asignaciones anuales de vacaciones HN en aniversarios laborales."""
        from datetime import date
        from dateutil.relativedelta import relativedelta

        today = date.today()
        LeaveAllocation = self.env['hr.leave.allocation']

        # Empleados activos con contrato
        employees = self.search([
            ('active', '=', True),
            ('contract_date_start', '!=', False),
        ])

        # 1) Temporales que terminan hoy: asignación proporcional si no completan año
        for emp in employees:
            vacation_type = emp._hn_primary_vacation_leave_type()
            if not vacation_type:
                continue
            if not emp.contract_date_start or not emp.contract_date_end:
                continue
            if emp.contract_date_end != today:
                continue
            plan = emp.hn_vacation_plan_id or emp._get_default_hn_vacation_plan()
            if not plan or not plan.allow_proportional:
                continue
            days_worked = (emp.contract_date_end - emp.contract_date_start).days
            if days_worked >= 360:
                continue  # Ya tiene año completo, se maneja en aniversario
            days_year1 = plan.get_days_for_seniority(1)
            if days_year1 <= 0:
                continue
            proportional_days = round((days_worked / 360.0) * days_year1, 1)
            if proportional_days <= 0:
                continue
            pending = LeaveAllocation.search([
                ('employee_id', '=', emp.id),
                ('holiday_status_id', '=', vacation_type.id),
                ('state', '=', 'validate'),
            ])
            if pending:
                continue  # Ya tiene asignación
            period_end = today + relativedelta(months=3)  # Período corto para temporales
            alloc = LeaveAllocation.sudo().create({
                'name': f'Vacaciones proporcionales temporal - {today.year}',
                'employee_id': emp.id,
                'holiday_status_id': vacation_type.id,
                'number_of_days': proportional_days,
                'date_from': today,
                'date_to': period_end,
                'hn_vacation_period_start': emp.contract_date_start,
                'hn_vacation_period_end': today,
                'hn_allow_accumulation': self._hn_plan_allows_allocation_stack(plan),
            })
            if alloc.state == 'confirm':
                alloc.sudo().action_approve()

        # 2–3) Plan anual: sincronizar asignaciones por cada año laboral (desde 1er aniversario)
        for emp in employees:
            vacation_type = emp._hn_primary_vacation_leave_type()
            if not vacation_type:
                continue
            start = emp.contract_date_start
            if not start:
                continue
            plan = emp.hn_vacation_plan_id or emp._get_default_hn_vacation_plan()
            if (emp.hn_is_temporary or emp.contract_date_end) and not emp.hn_vacation_plan_id:
                plan = self.env['gn.hn.vacation.plan'].search([
                    ('company_id', 'in', [False, (emp.company_id or self.env.company).id]),
                    ('is_temporary', '=', True),
                    ('active', '=', True),
                ], limit=1) or plan
            if not plan or plan.vacation_accrual_mode != 'annual':
                continue
            sync = emp._hn_sync_annual_allocations(plan, vacation_type, today)
            if sync['names']:
                emp._hn_refuse_first_year_proportional_allocations(vacation_type, start)
            is_anniv = start.day == today.day and start.month == today.month
            if is_anniv and relativedelta(today, start).years >= 1:
                if sync.get('blocked_current_by_pending'):
                    rem = sync.get('pending_remaining', 0.0)
                    emp.activity_schedule(
                        'l10n_hn_hr_payroll.mail_activity_hn_program_vacation',
                        date_deadline=today + relativedelta(months=3),
                        note=f'Vacaciones pendientes ({rem:.1f} días). Regularizar antes de generar nuevo período.',
                    )
                else:
                    emp.activity_schedule(
                        'l10n_hn_hr_payroll.mail_activity_hn_program_vacation',
                        date_deadline=today + relativedelta(months=3),
                        note=f'Definir época de vacaciones antes del {today + relativedelta(months=3)}.',
                    )

    @api.model
    def _cron_hn_vacation_monthly_proportional(self):
        """Cron diario: actualiza devengo en planes mensual o diario (una asignación por año laboral)."""
        from datetime import date
        from dateutil.relativedelta import relativedelta

        today = date.today()

        employees = self.search([
            ('active', '=', True),
            ('contract_date_start', '!=', False),
        ])
        for emp in employees:
            vacation_type = emp._hn_primary_vacation_leave_type()
            if not vacation_type:
                continue
            plan = emp.hn_vacation_plan_id or emp._get_default_hn_vacation_plan()
            if (emp.hn_is_temporary or emp.contract_date_end) and not emp.hn_vacation_plan_id:
                plan = self.env['gn.hn.vacation.plan'].search([
                    ('company_id', 'in', [False, (emp.company_id or self.env.company).id]),
                    ('is_temporary', '=', True),
                    ('active', '=', True),
                ], limit=1) or plan
            if not plan:
                continue
            mode = plan.vacation_accrual_mode
            if mode == 'monthly':
                emp._hn_sync_monthly_year_allocations(plan, vacation_type, today)
                continue
            if mode == 'daily':
                emp._hn_sync_daily_year_allocations(plan, vacation_type, today)
                continue

    @api.model
    def _cron_hn_vacation_notifications(self):
        """Cron diario: envía notificaciones con las plantillas de email HN.
        - Aniversario próximo (30 días antes)
        - Alerta 3 meses sin programar
        """
        today = date.today()

        # 1) Aniversario próximo: empleados cuyo aniversario es en ~30 días
        tpl_anniversary = self.env.ref(
            'l10n_hn_hr_payroll.mail_template_hn_anniversary', raise_if_not_found=False
        )
        if tpl_anniversary:
            target = today + relativedelta(days=30)
            employees = self.search([
                ('active', '=', True),
                ('contract_date_start', '!=', False),
            ])
            for emp in employees:
                start = emp.contract_date_start
                if start.day == target.day and start.month == target.month:
                    years = relativedelta(target, start).years
                    if years >= 1:
                        try:
                            tpl_anniversary.send_mail_payroll_tracked(emp.id, force_send=True)
                        except Exception:
                            pass

        # 2) 3 meses sin programar: asignaciones con > 0 saldo y period_start + 3m = hoy
        tpl_3months = self.env.ref(
            'l10n_hn_hr_payroll.mail_template_hn_3months_expiry', raise_if_not_found=False
        )
        if tpl_3months:
            LeaveType = self.env['hr.leave.type']
            allocations = self.env['hr.leave.allocation'].search([
                ('holiday_status_id.gn_vacation_is_primary', '=', True),
                ('state', '=', 'validate'),
                ('hn_vacation_period_start', '!=', False),
            ])
            for alloc in allocations:
                emp = alloc.employee_id
                if not emp:
                    continue
                lt = LeaveType.gn_primary_vacation_leave_type(emp.company_id or self.env.company)
                if not lt or alloc.holiday_status_id.id != lt.id:
                    continue
                deadline = alloc.hn_vacation_period_start + relativedelta(months=3)
                if deadline == today:
                    remaining = alloc.number_of_days - alloc.leaves_taken
                    if remaining > 0:
                        emp = alloc.employee_id
                        if emp and emp.active:
                            try:
                                tpl_3months.send_mail_payroll_tracked(emp.id, force_send=True)
                            except Exception:
                                pass

    def _hn_vacation_daily_rate(self, ref_date=None):
        """Tasa diaria para cálculo de vacaciones (promedio salarial).
        Por ahora usa contract_wage/30. Se ampliará con gn.hn.vacation.salary.map."""
        self.ensure_one()
        ref_date = ref_date or date.today()
        version = self._get_version(ref_date) if hasattr(self, '_get_version') else self.version_id
        if not version:
            return 0.0
        wage = getattr(version, 'contract_wage', 0) or getattr(version, 'wage', 0)
        if not wage:
            return 0.0
        return wage / 30.0

    def _hn_vac_payroll_monthly_equivalent_wage(self, version):
        if not version:
            return 0.0
        wage = float(getattr(version, 'contract_wage', 0) or version.wage or 0.0)
        if not wage:
            return 0.0
        sp = version.schedule_pay or (
            version.structure_type_id.default_schedule_pay if version.structure_type_id else None
        )
        if sp == 'bi-weekly':
            return wage * 2.0
        return wage

    def _hn_vacation_payroll_salary_average_6m(self, ref_date=None):
        self.ensure_one()
        ref_date = ref_date or fields.Date.today()
        History = self.env['l10n.hn.employee.monthly.salary.history']
        total = 0.0
        n = 0
        d = date(ref_date.year, ref_date.month, 1)
        for i in range(1, 7):
            cur = d - relativedelta(months=i)
            hist = History.search([
                ('employee_id', '=', self.id),
                ('year', '=', cur.year),
                ('month', '=', cur.month),
            ], limit=1)
            if hist:
                total += hist.amount_monthly_display or 0.0
                n += 1
                continue
            month_end = date(cur.year, cur.month, monthrange(cur.year, cur.month)[1])
            ver = self._get_version(month_end)
            monthly = self._hn_vac_payroll_monthly_equivalent_wage(ver)
            if monthly:
                total += monthly
                n += 1
        if not n:
            return 0.0
        return total / n

    def _hn_vacation_payroll_salary_average_6m_plus_commission(self, ref_date=None):
        """Promedio de 6 meses para reportes: en historial HN siempre salario base + comisiones del mes."""
        self.ensure_one()
        ref_date = ref_date or fields.Date.today()
        History = self.env['l10n.hn.employee.monthly.salary.history']
        total = 0.0
        n = 0
        d = date(ref_date.year, ref_date.month, 1)
        for i in range(1, 7):
            cur = d - relativedelta(months=i)
            hist = History.search([
                ('employee_id', '=', self.id),
                ('year', '=', cur.year),
                ('month', '=', cur.month),
            ], limit=1)
            if hist:
                total += (hist.amount_net or 0.0) + (hist.amount_commission or 0.0)
                n += 1
                continue
            month_end = date(cur.year, cur.month, monthrange(cur.year, cur.month)[1])
            ver = self._get_version(month_end)
            monthly = self._hn_vac_payroll_monthly_equivalent_wage(ver)
            if monthly:
                total += monthly
                n += 1
        if not n:
            return 0.0
        return total / n

    def _hn_vacation_payroll_daily_from_average(self, ref_date=None):
        """Promedio diario para liquidación vacaciones HN (misma fórmula que regla HN_VAC_PAY)."""
        self.ensure_one()
        ref_date = ref_date or fields.Date.today()
        prom = self._hn_vacation_payroll_salary_average_6m(ref_date)
        if not prom:
            return 0.0
        return (prom * 14.0 / 12.0) / 30.0

    def _hn_vacation_devengados_at(self, ref_date):
        """Días devengados teóricos a una fecha (p. ej. 31-dic del cierre): misma lógica que «días que le
        corresponden» en vacaciones HN, pero usando ref_date en lugar del día actual."""
        self.ensure_one()
        if not ref_date or not self.contract_date_start or self.contract_date_start > ref_date:
            return 0.0
        plan = self.hn_vacation_plan_id or self._get_default_hn_vacation_plan()
        if not plan:
            return 0.0
        delta = relativedelta(ref_date, self.contract_date_start)
        years = delta.years
        mode = plan.vacation_accrual_mode
        if mode in ('monthly', 'daily'):
            hire = self.contract_date_start
            if not hire or ref_date < hire:
                return 0.0
            total = 0.0
            for _k, p_start, p_end in self._hn_iter_vacation_periods(hire, ref_date, plan):
                days_full = float(self._hn_period_days_entitled(plan, hire, p_start, p_end))
                if mode == 'monthly':
                    total += self._hn_monthly_target_days_in_period(p_start, p_end, ref_date, days_full)
                else:
                    total += self._hn_daily_target_days_in_period(p_start, p_end, ref_date, days_full)
            return float(total)
        if mode == 'annual':
            if getattr(plan, 'vacation_year_basis', 'labor') == 'civil':
                hire = self.contract_date_start
                if not hire or ref_date < hire:
                    return 0.0
                total = 0.0
                for _y in range(hire.year, ref_date.year + 1):
                    dec = date(_y, 12, 31)
                    ps = max(hire, date(_y, 1, 1))
                    if ps > ref_date:
                        break
                    if dec > ref_date:
                        continue
                    total += float(self._hn_period_days_entitled(plan, hire, ps, dec))
                return float(total)
            if years < 1:
                return 0.0
            return float(plan.get_days_for_seniority(years))
        return 0.0

    def _hn_vacation_tenure_calendar_days_end(self, end_date):
        """Días naturales desde ingreso hasta end_date inclusive; tope en fecha de salida si aplica."""
        self.ensure_one()
        if not self.contract_date_start or not end_date:
            return 0
        hire = self.contract_date_start
        if hire > end_date:
            return 0
        end = end_date
        dep = self.departure_date
        if dep and hire <= dep <= end_date:
            end = dep
        return (end - hire).days + 1

    def _hn_vacation_calendar_days_worked_year(self, year):
        """Días naturales trabajados en el año civil (desde el ingreso o 1-ene hasta 31-dic o salida)."""
        self.ensure_one()
        year_start = date(year, 1, 1)
        year_end = date(year, 12, monthrange(year, 12)[1])
        if not self.contract_date_start:
            return 0
        hire = self.contract_date_start
        if hire > year_end:
            return 0
        start = max(year_start, hire)
        end = year_end
        dep = self.departure_date
        if dep and year_start <= dep <= year_end:
            end = min(end, dep)
        if start > end:
            return 0
        return (end - start).days + 1

    def _hn_vacation_payroll_advance_days_year(self, year):
        """Suma hn_advance_days en solicitudes de vacaciones HN validadas con inicio en el año."""
        self.ensure_one()
        year_start = date(year, 1, 1)
        year_end = date(year, 12, monthrange(year, 12)[1])
        Leave = self.env['hr.leave']
        lt = self._hn_primary_vacation_leave_type()
        if not lt:
            return 0.0
        leaves = Leave.search([
            ('employee_id', '=', self.id),
            ('holiday_status_id', '=', lt.id),
            ('state', 'in', ('validate', 'validate1')),
            ('request_date_from', '>=', year_start),
            ('request_date_from', '<=', year_end),
        ])
        return float(sum(leaves.mapped('hn_advance_days')))

    def _hn_vacation_payroll_remaining_hn_days(self):
        """Saldo para solicitar tiempo libre (asignación − gozados − liquidado nómina)."""
        self.ensure_one()
        Allocation = self.env['hr.leave.allocation']
        lt = self._hn_primary_vacation_leave_type()
        if not lt:
            return 0.0
        allocs = Allocation.search([
            ('employee_id', '=', self.id),
            ('holiday_status_id', '=', lt.id),
            ('state', '=', 'validate'),
        ])
        total = 0.0
        for alloc in allocs:
            settled = alloc.hn_vac_payroll_settled_days or 0.0
            rem = (alloc.number_of_days or 0.0) - (alloc.leaves_taken or 0.0) - settled
            if rem > 0:
                total += rem
        return total

    def _hn_vacation_payroll_accrued_cash_days(self):
        """Días de vacaciones HN a pagar en nómina de vacaciones: asignación validada menos
        solo lo liquidado vía hn_vac_payroll_settled_days. No resta leaves_taken: los días
        gozados se reflejan en la nómina regular, no reducen el importe de esta liquidación."""
        self.ensure_one()
        Allocation = self.env['hr.leave.allocation']
        lt = self._hn_primary_vacation_leave_type()
        if not lt:
            return 0.0
        allocs = Allocation.search([
            ('employee_id', '=', self.id),
            ('holiday_status_id', '=', lt.id),
            ('state', '=', 'validate'),
        ])
        total = 0.0
        for alloc in allocs:
            settled = alloc.hn_vac_payroll_settled_days or 0.0
            rem = (alloc.number_of_days or 0.0) - settled
            if rem > 0:
                total += rem
        return total

    def _hn_vacation_payroll_payable_days(self, payslip):
        self.ensure_one()
        struct = payslip.struct_id
        kind = struct.hn_vacation_payroll_kind if struct else False
        if not kind:
            return 0.0
        accrued = self._hn_vacation_payroll_accrued_cash_days()
        if accrued <= 0:
            return 0.0
        if kind == 'anniversary_month':
            if not self.contract_date_start or self.contract_date_start.month != payslip.date_from.month:
                return 0.0
        elif kind == 'year_end_december':
            if not payslip.date_from or not payslip.date_to:
                return 0.0
            if payslip.date_from.year != payslip.date_to.year:
                return 0.0
            if payslip.date_from.month != 1 or payslip.date_from.day != 1:
                return 0.0
            dec_last = monthrange(payslip.date_to.year, 12)[1]
            if payslip.date_to.month != 12 or payslip.date_to.day != dec_last:
                return 0.0
            if self.contract_date_start and self.contract_date_start.month == 12:
                return 0.0
        return accrued

    def _hn_vacation_payroll_settle_allocations(self, days):
        """FIFO sobre asignaciones HN validadas. Devuelve [{'allocation_id': int, 'days': float}, ...]"""
        self.ensure_one()
        if days <= 0:
            return []
        Allocation = self.env['hr.leave.allocation']
        lt = self._hn_primary_vacation_leave_type()
        if not lt:
            return []
        allocs = Allocation.search([
            ('employee_id', '=', self.id),
            ('holiday_status_id', '=', lt.id),
            ('state', '=', 'validate'),
        ], order='date_from asc, id asc')
        remaining_to_settle = float(days)
        applied = []
        for alloc in allocs:
            if remaining_to_settle <= 1e-9:
                break
            settled = alloc.hn_vac_payroll_settled_days or 0.0
            avail = (alloc.number_of_days or 0.0) - settled
            if avail <= 0:
                continue
            take = min(avail, remaining_to_settle)
            alloc.hn_vac_payroll_settled_days = settled + take
            applied.append({'allocation_id': alloc.id, 'days': round(take, 4)})
            remaining_to_settle -= take
        if remaining_to_settle > 1e-6:
            raise UserError(
                _('No hay suficientes días de vacaciones HN para liquidar %.4f días en %s.')
                % (days, self.name)
            )
        return applied

    def _get_default_hn_vacation_plan(self):
        """Obtiene el plan por defecto de la compañía."""
        self.ensure_one()
        company = self.company_id or self.env.company
        if company.hn_default_vacation_plan_id:
            return company.hn_default_vacation_plan_id
        return self.env['gn.hn.vacation.plan'].search([
            ('company_id', 'in', [False, company.id]),
            ('is_temporary', '=', False),
            ('active', '=', True),
        ], limit=1)

    def _gn_collective_vacation_initial_adjustment(self):
        self.ensure_one()
        return self.hn_initial_vacation_taken_display or 0.0
