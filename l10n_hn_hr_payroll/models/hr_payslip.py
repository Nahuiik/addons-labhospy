# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

import math
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayslip(models.Model):
    """Extend hr.payslip for Honduras payroll localization"""
    _inherit = 'hr.payslip'
    
    # IHSS information
    ihss_ivm_employee = fields.Float(string='IHSS IVM Employee', digits=(12, 2))
    ihss_ivm_employer = fields.Float(string='IHSS IVM Employer', digits=(12, 2))
    ihss_em_employee = fields.Float(string='IHSS EM Employee', digits=(12, 2))
    ihss_em_employer = fields.Float(string='IHSS EM Employer', digits=(12, 2))
    ihss_base = fields.Float(string='IHSS Base', digits=(12, 2))
    
    # RAP information
    rap_foviif_employee = fields.Float(string='RAP Employee', digits=(12, 2))
    rap_foviif_employer = fields.Float(string='RAP Employer', digits=(12, 2))
    rap_frl_employer = fields.Float(string='RAP FRL Employer', digits=(12, 2))
    rap_base = fields.Float(string='RAP Base', digits=(12, 2))
    
    # ISR information
    isr_amount = fields.Float(string='ISR Amount', digits=(12, 2))
    isr_base = fields.Float(string='ISR Taxable Base', digits=(12, 2))
    isr_ytd = fields.Float(string='ISR YTD', digits=(12, 2))
    
    # Benefits
    thirteenth_month_amount = fields.Float(string='13th Month Amount', digits=(12, 2))
    fourteenth_month_amount = fields.Float(string='14th Month Amount', digits=(12, 2))
    
    # Period information
    period_days = fields.Integer(string='Period Days', compute='_compute_period_days', store=True)
    # Días efectivos a pagar (considerando fecha de ingreso). Meses = 30 días.
    effective_period_days = fields.Integer(
        string='Días Efectivos',
        compute='_compute_effective_period_days',
        store=True,
        help='Días del período que corresponden pagar al empleado según su fecha de ingreso. '
             'Todos los meses se consideran de 30 días.',
    )
    # Días estándar del período (30 mensual, 15 quincenal) para prorrateo.
    standard_period_days = fields.Integer(
        string='Días Estándar Período',
        compute='_compute_effective_period_days',
        store=True,
        help='Días del período según convención Honduras: 30 mensual, 15 quincenal.',
    )
    # Días a pagar = días en contrato - ausencias no pagadas. Usar para salario base.
    payable_period_days = fields.Integer(
        string='Días a Pagar',
        compute='_compute_effective_period_days',
        store=True,
        help='Días del período a pagar: días en contrato menos solo ausencias sin goce. '
             'Las vacaciones y otras ausencias pagadas no se restan. '
             'Referencia; el salario base usa hn_contract_period_days y descuentos aparte.',
    )
    hn_contract_period_days = fields.Integer(
        string='Días contrato en período',
        compute='_compute_effective_period_days',
        store=True,
        help='Días del estándar del recibo (15/30) efectivamente cubiertos por el contrato en el período, '
             'sin restar ausencias. Para regla BASIC; sin goce se descuenta con valor día = wage/30.',
    )

    # Incapacidad IHSS - días calendario en el período (para reglas salariales)
    hn_incap_days_patrono_cal = fields.Integer(
        string='Días Incap. Patrono (cal)',
        compute='_compute_hn_incap_days',
        help='Días calendario de incapacidad IHSS pagados por patrono (días 1-3) en este período.',
    )
    hn_incap_days_ihss_cal = fields.Integer(
        string='Días Incap. IHSS (cal)',
        compute='_compute_hn_incap_days',
        help='Días calendario de incapacidad IHSS con subsidio IHSS (día 4+) en este período.',
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to automatically add recurring concepts as inputs"""
        # Ensure name is set before create if possible
        for vals in vals_list:
            if 'name' not in vals and 'employee_id' in vals and 'date_from' in vals and 'date_to' in vals:
                # Try to compute name before create
                employee = self.env['hr.employee'].browse(vals['employee_id'])
                struct = self.env['hr.payroll.structure'].browse(vals.get('struct_id', False)) if vals.get('struct_id') else False
                if employee and struct:
                    # Generate a temporary name
                    date_from = vals['date_from']
                    date_to = vals['date_to']
                    payslip_name = struct.payslip_name or 'Salary Slip'
                    vals['name'] = f'{payslip_name} - {employee.name or ""} - {date_from} to {date_to}'
        
        payslips = super().create(vals_list)
        for payslip in payslips:
            # Recompute name to ensure it's correct
            if payslip.employee_id and payslip.date_from and payslip.date_to:
                payslip._compute_name()
                payslip._sync_recurring_concepts()
            # Limpiar flag de incluir en nómina cuando se genera el recibo
            if (payslip.employee_id and not payslip.employee_id.active
                    and getattr(payslip.employee_id, 'include_in_current_payroll', False)):
                payslip.employee_id.include_in_current_payroll = False
        return payslips
    
    # NOTE: single write() override is defined below (after _update_isr_ytd)
    # to combine recurring concept sync + ISR YTD update + OI reset.
    
    def _sync_recurring_concepts(self):
        """Delega conceptos recurrentes al módulo compartido y sincroniza entradas de planilla HN."""
        self.ensure_one()
        self._gn_sync_recurring_concepts_inputs()
        self._sync_planilla_inputs()

    def _get_version_for_period(self, employee, date_from, date_to):
        """Versión de contrato activa durante el período (no current_version_id, que puede ser otra)."""
        if not employee or not date_from or not date_to:
            return self.env['hr.version']
        return self.env['hr.version'].search([
            ('employee_id', '=', employee.id),
            ('contract_date_start', '<=', date_to),
            '|', ('contract_date_end', '=', False), ('contract_date_end', '>=', date_from),
        ], order='contract_date_start desc', limit=1)

    def _sync_planilla_inputs(self):
        """Sincronizar HOR_EXT y OI desde planilla para el período del payslip.

        IMPORTANTE: Reemplaza (no suma) los montos para evitar doble conteo cuando
        compute_sheet llama _sync_recurring_concepts múltiples veces.
        OI se obtiene de planillas TE que traslapan el período, no de version.amount_other_income
        (que puede tener datos obsoletos de períodos anteriores).
        """
        self.ensure_one()
        if not self.employee_id or not self.date_from or not self.date_to:
            return
        version = self._get_version_for_period(self.employee_id, self.date_from, self.date_to)
        if not version:
            return

        company_id = self.company_id.id if self.company_id else None

        # HOR_EXT: suma de registros HE donde planilla traslapa período del payslip
        he_amount = 0.0
        if 'l10n.hn.extra.hours.register' in self.env:
            registers = self.env['l10n.hn.extra.hours.register'].search([
                ('version_id', '=', version.id),
            ])
            for reg in registers:
                sheet = reg.payroll_sheet_id
                if not sheet or sheet.state != 'done':
                    continue
                if company_id and sheet.company_id and sheet.company_id.id != company_id:
                    continue
                if sheet.date_start and sheet.date_end:
                    if sheet.date_start <= self.date_to and sheet.date_end >= self.date_from:
                        he_amount += (reg.amount_25 or 0) + (reg.amount_50 or 0) + (reg.amount_75 or 0) + (reg.amount_100 or 0)

        # OI: suma de líneas TE de planillas que traslapan el período (no version.amount_other_income)
        oi_amount = 0.0
        if 'l10n.hn.payroll.line.te' in self.env:
            te_lines = self.env['l10n.hn.payroll.line.te'].search([
                ('employee_id', '=', self.employee_id.id),
                ('parent_id.state', '=', 'done'),
                ('parent_id.date_start', '<=', self.date_to),
                ('parent_id.date_end', '>=', self.date_from),
            ])
            for line in te_lines:
                if company_id and line.parent_id.company_id and line.parent_id.company_id.id != company_id:
                    continue
                oi_amount += line.amount_other_income or 0

        # REEMPLAZAR (no sumar) para evitar doble conteo en compute_sheet
        input_type_he = self._get_or_create_input_type('HOR_EXT', _('Horas Extra'))
        existing_he = self.input_line_ids.filtered(lambda l: l.input_type_id.code == 'HOR_EXT')
        if he_amount != 0:
            if existing_he:
                existing_he[0].write({'amount': he_amount})
            else:
                self.write({
                    'input_line_ids': [(0, 0, {
                        'name': _('Horas Extra'),
                        'input_type_id': input_type_he.id,
                        'amount': he_amount,
                    })]
                })
        elif existing_he:
            existing_he[0].write({'amount': 0.0})

        input_type_oi = self._get_or_create_input_type('OI', _('Otros Ingresos'))
        existing_oi = self.input_line_ids.filtered(lambda l: l.input_type_id.code == 'OI')
        if oi_amount != 0:
            if existing_oi:
                existing_oi[0].write({'amount': oi_amount})
            else:
                self.write({
                    'input_line_ids': [(0, 0, {
                        'name': _('Otros Ingresos'),
                        'input_type_id': input_type_oi.id,
                        'amount': oi_amount,
                    })]
                })
        elif existing_oi:
            existing_oi[0].write({'amount': 0.0})

    # NOTE: single compute_sheet() override is defined below (after _update_isr_ytd)
    # to combine worked-days refresh + post-compute recurring concept sync.
    
    @api.depends('employee_id', 'date_from', 'date_to')
    def _compute_hn_incap_days(self):
        """Suma días calendario de incapacidad IHSS del empleado en el período del payslip.
        Solo cuenta los días que caen dentro del rango date_from..date_to del payslip."""
        for slip in self:
            slip.hn_incap_days_patrono_cal = 0
            slip.hn_incap_days_ihss_cal = 0
            if not slip.employee_id or not slip.date_from or not slip.date_to:
                continue
            leaves = self.env['hr.leave'].sudo().search([
                ('employee_id', '=', slip.employee_id.id),
                ('holiday_status_id.is_ihss_incapacity', '=', True),
                ('state', 'in', ('validate', 'validate1')),
                ('date_from', '<=', slip.date_to),
                ('date_to', '>=', slip.date_from),
            ])
            for leave in leaves:
                leave_from = fields.Date.to_date(leave.date_from)
                leave_to = fields.Date.to_date(leave.date_to)
                overlap_start = max(leave_from, slip.date_from)
                overlap_end = min(leave_to, slip.date_to)
                day_index_start = leave.hn_incap_day_index_start or 1
                current = overlap_start
                while current <= overlap_end:
                    delta = (current - leave_from).days
                    case_day = day_index_start + delta
                    if case_day <= 3:
                        slip.hn_incap_days_patrono_cal += 1
                    else:
                        slip.hn_incap_days_ihss_cal += 1
                    current += timedelta(days=1)

    @api.depends('date_from', 'date_to')
    def _compute_period_days(self):
        """Calculate number of days in payslip period (calendar days)"""
        for slip in self:
            if slip.date_from and slip.date_to:
                delta = slip.date_to - slip.date_from
                slip.period_days = delta.days + 1
            else:
                slip.period_days = 0

    @api.depends(
        'date_from', 'date_to', 'employee_id', 'struct_id',
        'worked_days_line_ids', 'worked_days_line_ids.number_of_days',
        'worked_days_line_ids.work_entry_type_id', 'worked_days_line_ids.work_entry_type_id.is_leave',
    )
    def _compute_effective_period_days(self):
        """Días efectivos = días en contrato - total ausencias.
        Días a pagar = días en contrato - solo ausencias no pagadas (para salario base).
        Considera fecha de ingreso (contract_date_start) y salida (contract_date_end)."""
        for slip in self:
            if not slip.date_from or not slip.date_to:
                slip.effective_period_days = 0
                slip.standard_period_days = 30
                slip.payable_period_days = 0
                slip.hn_contract_period_days = 0
                continue
            # Días estándar del período: 30 mensual, 15 quincenal
            struct = slip.struct_id
            is_biweekly = False
            if struct:
                p = struct.periodicity if 'periodicity' in struct._fields else None
                if p in ('biweekly', 'bi-weekly'):
                    is_biweekly = True
                elif struct.type_id:
                    sched = struct.type_id.default_schedule_pay or 'monthly'
                    is_biweekly = sched in ('bi-weekly', 'biweekly')
            std = 15 if is_biweekly else 30
            slip.standard_period_days = std
            # Días en contrato durante el período (empleado que ingresa/sale a mitad de período)
            days_in_contract = std
            if slip.employee_id:
                version = slip._get_version_for_period(
                    slip.employee_id, slip.date_from, slip.date_to
                )
                if version:
                    eff_start = max(slip.date_from, version.contract_date_start)
                    eff_end = (
                        min(slip.date_to, version.contract_date_end)
                        if version.contract_date_end
                        else slip.date_to
                    )
                    if eff_start <= eff_end:
                        days_in_contract = (eff_end - eff_start).days + 1
                    else:
                        days_in_contract = 0
            # Limitar a días estándar (15 quincenal, 30 mensual) para que el descuento
            # por ausencias sin goce sea correcto (ej: 2da quincena marzo tiene 16 días
            # calendario pero se paga como 15; 1 día sin pagar debe dar 14 días a pagar).
            days_in_contract = min(days_in_contract, std)
            slip.hn_contract_period_days = max(0, int(days_in_contract))
            # Total de ausencias (todas: pagadas y sin goce)
            total_absence_days = 0.0
            unpaid_absence_days = 0.0
            if struct and struct.use_worked_day_lines and slip.worked_days_line_ids:
                unpaid_ids = set()
                if getattr(struct, 'unpaid_work_entry_type_ids', None):
                    unpaid_ids = set(struct.unpaid_work_entry_type_ids.ids)
                for wd in slip.worked_days_line_ids:
                    if not wd.work_entry_type_id or not getattr(wd.work_entry_type_id, 'is_leave', False):
                        continue
                    days_val = abs(wd.number_of_days or 0)
                    total_absence_days += days_val
                    if wd.work_entry_type_id.id in unpaid_ids:
                        unpaid_absence_days += days_val
            # Días efectivos = días en contrato - todas las ausencias (enteros; medios días vía redondeo hacia arriba)
            slip.effective_period_days = max(
                0,
                int(days_in_contract) - int(math.ceil(float(total_absence_days) - 1e-9)),
            )
            # Días a pagar = contrato - sin goce (ceil para no ignorar medios días en entradas de trabajo)
            slip.payable_period_days = max(
                0,
                int(days_in_contract) - int(math.ceil(float(unpaid_absence_days) - 1e-9)),
            )
    
    @api.model
    def _schedule_timedelta(self, schedule, date_from, country_code=False):
        """Duración de período por tipo de nómina (paridad con hr_payroll Enterprise).

        En HN, bi-weekly es quincena calendario (cortes 1–15 y 16–fin), no 14 días fijos.
        `l10n_hn_payroll_base` no define este helper; la implementación completa vive aquí.
        """
        if schedule == 'quarterly':
            return relativedelta(months=3, days=-1)
        if schedule == 'semi-annually':
            return relativedelta(months=6, days=-1)
        if schedule == 'annually':
            return relativedelta(years=1, days=-1)
        if schedule == 'weekly':
            return relativedelta(days=6)
        if schedule == 'bi-weekly':
            if not country_code:
                if self.company_id and self.company_id.country_id:
                    country_code = self.company_id.country_id.code
                elif self.env.company.country_id:
                    country_code = self.env.company.country_id.code
            if country_code == 'HN':
                return relativedelta(day=15 if date_from.day <= 15 else 31)
            return relativedelta(days=13)
        if schedule == 'semi-monthly':
            return relativedelta(day=15 if date_from.day < 15 else 31)
        if schedule == 'bi-monthly':
            return relativedelta(months=2, days=-1)
        if schedule == 'daily':
            return relativedelta(days=0)
        return relativedelta(months=1, days=-1)
    
    def write(self, vals):
        """Unified write: sync recurring concepts on employee/date change,
        update ISR YTD on confirmation, reset OI on done."""
        result = super().write(vals)

        if not self.env.context.get('_skip_recurring_sync'):
            if 'employee_id' in vals or 'date_from' in vals or 'date_to' in vals:
                for payslip in self:
                    if payslip.employee_id and payslip.date_from and payslip.date_to:
                        payslip._sync_recurring_concepts()

        if 'state' in vals and vals['state'] in ('done', 'paid'):
            for payslip in self:
                if payslip.state in ('done', 'paid'):
                    self._update_isr_ytd(payslip)

        return result
    
    def _update_isr_ytd(self, payslip):
        """Actualizar ISR retenido YTD en hr.version recalculando desde cero"""
        if not payslip.employee_id:
            return
        version = self._get_version_for_period(
            payslip.employee_id, payslip.date_from, payslip.date_to
        )
        if not version:
            version = payslip.employee_id.current_version_id.sudo() if payslip.employee_id.current_version_id else False
        if not version:
            return
        year = payslip.date_to.year if payslip.date_to else fields.Date.today().year
        
        # Recalcular YTD desde cero basándose en todos los payslips confirmados del año
        year_start = fields.Date.today().replace(year=year, month=1, day=1)
        year_end = fields.Date.today().replace(year=year, month=12, day=31)
        
        payslips_ytd = self.env['hr.payslip'].search([
            ('employee_id', '=', payslip.employee_id.id),
            ('date_to', '>=', year_start),
            ('date_to', '<=', year_end),
            ('state', 'in', ['done', 'paid']),
        ])
        
        # Sumar ISR de todos los payslips confirmados
        total_isr_ytd = 0.0
        for slip in payslips_ytd:
            isr_line = slip.line_ids.filtered(lambda l: l.code == 'ISR')
            if isr_line:
                total_isr_ytd += abs(isr_line[0].total)
        
        # Actualizar YTD
        version.isr_retenido_ytd = total_isr_ytd
    
    def compute_sheet(self):
        """Unified compute_sheet: refresh worked days from work entries,
        then compute, then re-sync percentage-based recurring concepts."""
        payslips = self.filtered(lambda s: s.state == 'draft')
        to_refresh = payslips.filtered(
            lambda s: s.struct_id
            and s.struct_id.use_worked_day_lines
            and s.employee_id
            and s.version_id
            and not s.edited
        )
        if to_refresh:
            to_refresh.mapped('worked_days_line_ids').unlink()
            to_refresh._compute_worked_days_line_ids()

        result = super().compute_sheet()

        for payslip in self:
            if payslip.employee_id and payslip.date_from and payslip.date_to:
                payslip._sync_recurring_concepts()

        return result

    def _get_schedule_timedelta(self):
        """Override to pass country_code to _schedule_timedelta"""
        self.ensure_one()
        schedule = self.version_id.schedule_pay or self.version_id.structure_type_id.default_schedule_pay
        # Get country code from company
        country_code = False
        if self.company_id and self.company_id.country_id:
            country_code = self.company_id.country_id.code
        return self._schedule_timedelta(schedule, self.date_from, country_code)

    def _calculate_days_30_day_months(self, start_date, end_date):
        """Días entre dos fechas usando meses de 30 días (ley Honduras)."""
        if not start_date or not end_date or start_date > end_date:
            return 0
        if start_date.year == end_date.year and start_date.month == end_date.month:
            days = end_date.day - start_date.day + 1
            return min(days, 30)
        total_months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
        days_start_month = 30 - start_date.day + 1
        days_end_month = end_date.day
        if total_months == 1:
            return days_start_month + days_end_month
        full_months = max(0, total_months - 1)
        return days_start_month + (full_months * 30) + days_end_month

    def _get_report_days_worked(self):
        """Días trabajados = días calendario del período (30 días/mes) - ausencias no pagadas."""
        self.ensure_one()
        if not self.date_from or not self.date_to:
            return 0
        calendar_days = self._calculate_days_30_day_months(self.date_from, self.date_to)
        unpaid_days = sum(
            wd.number_of_days for wd in self.worked_days_line_ids
            if not getattr(wd, 'is_paid', True)
        )
        return max(0, calendar_days - abs(unpaid_days))

    def _get_report_hours_worked(self):
        """Horas trabajadas según ley: días trabajados × 8 horas diarias."""
        self.ensure_one()
        return self._get_report_days_worked() * 8

    def _get_report_he_breakdown(self):
        """Desglose de horas extra 25%, 50%, 75%, 100% desde planilla (cantidades y montos)."""
        self.ensure_one()
        result = {
            'he_25': 0.0, 'he_50': 0.0, 'he_75': 0.0, 'he_100': 0.0,
            'amount_25': 0.0, 'amount_50': 0.0, 'amount_75': 0.0, 'amount_100': 0.0,
        }
        if 'l10n.hn.extra.hours.register' not in self.env:
            return result
        version = self._get_version_for_period(self.employee_id, self.date_from, self.date_to)
        if not version:
            return result
        company_id = self.company_id.id if self.company_id else None
        for reg in self.env['l10n.hn.extra.hours.register'].search([('version_id', '=', version.id)]):
            sheet = reg.payroll_sheet_id
            if not sheet or sheet.state != 'done':
                continue
            if company_id and sheet.company_id and sheet.company_id.id != company_id:
                continue
            if sheet.date_start and sheet.date_end and sheet.date_start <= self.date_to and sheet.date_end >= self.date_from:
                result['he_25'] += reg.he_25 or 0
                result['he_50'] += reg.he_50 or 0
                result['he_75'] += reg.he_75 or 0
                result['he_100'] += reg.he_100 or 0
                result['amount_25'] += reg.amount_25 or 0
                result['amount_50'] += reg.amount_50 or 0
                result['amount_75'] += reg.amount_75 or 0
                result['amount_100'] += reg.amount_100 or 0
        return result

    def _get_report_te_amount(self):
        """Recargo de turno nocturno desde planilla TE (Turnos Extra)."""
        self.ensure_one()
        if 'l10n.hn.payroll.line.te' not in self.env:
            return 0.0
        if not self.employee_id or not self.date_from or not self.date_to:
            return 0.0
        company_id = self.company_id.id if self.company_id else None
        domain = [
            ('employee_id', '=', self.employee_id.id),
            ('parent_id.state', '=', 'done'),
            ('parent_id.date_start', '<=', self.date_to),
            ('parent_id.date_end', '>=', self.date_from),
        ]
        if company_id:
            domain.append(('parent_id.company_id', '=', company_id))
        lines = self.env['l10n.hn.payroll.line.te'].search(domain)
        return sum(l.amount_other_income or 0 for l in lines)

    @api.model
    def get_payroll_dashboard_data(self):
        """Extiende el hub CE con conteo de empleados (vista dashboard HN)."""
        data = super().get_payroll_dashboard_data()
        company = self.env.company
        data['employee_count'] = self.env['hr.employee'].search_count([
            ('company_id', 'child_of', company.id),
        ])
        return data

    @api.model
    def get_l10n_hn_dashboard_data(self):
        """Return Honduras-specific dashboard data: planillas, last period status, wizard action."""
        result = {
            'planilla_stats': [],
            'last_period_status': None,
            'wizard_action': 'l10n_hn_hr_payroll.action_payroll_generation_wizard',
        }
        # Planillas HE/TE/BD confirmadas del período actual
        Period = self.env.get('l10n.hn.payroll.period')
        Sheet = self.env.get('l10n.hn.payroll.sheet')
        if not Period or not Sheet:
            return result
        try:
            period = Period.get_current_period()
            if period:
                sheets = Sheet.search([
                    ('payroll_period_id', '=', period.id),
                    ('state', '=', 'done'),
                ], limit=10)
                result['planilla_stats'] = [{
                    'id': s.id,
                    'name': s.name,
                    'total_he': s.total_he,
                    'total_te': s.total_te,
                    'total_bd': s.total_bd,
                } for s in sheets]
                result['current_period_name'] = period.name
        except Exception:
            pass
        # Last payslip run status (bi-weekly)
        PayslipRun = self.env['hr.payslip.run']
        last_run = PayslipRun.search([
            ('schedule_pay', '=', 'bi-weekly'),
            ('company_id', '=', self.env.company.id),
        ], order='date_end desc', limit=1)
        if last_run:
            result['last_period_status'] = {
                'name': last_run.name,
                'state': last_run.state,
                'payslip_count': last_run.payslip_count,
                'id': last_run.id,
            }
        return result