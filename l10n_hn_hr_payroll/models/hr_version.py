# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, timedelta


class HrVersion(models.Model):
    """Extend hr.version to add payment periodicity for Honduras payroll"""
    _inherit = 'hr.version'

    departure_specific_reason_id = fields.Many2one(
        'l10n.hn.hr.departure.specific.reason',
        string='Motivo específico',
        groups='hr.group_hr_user',
        copy=False,
        ondelete='restrict',
        tracking=True,
        help='Detalle del motivo de baja (catálogo Honduras).',
    )
    
    # Payment periodicity (for payroll calculations)
    periodicity = fields.Selection([
        ('weekly', 'Weekly'),
        ('biweekly', 'Biweekly'),
        ('monthly', 'Monthly'),
    ], string='Payment Periodicity', 
       compute='_compute_periodicity', store=True, readonly=False,
       help='Payment periodicity for payroll calculations. Used to adjust salary calculations for biweekly/weekly payrolls.',
       tracking=True)
    
    # Deductions information (computed from employee and settings)
    ihss_excluded = fields.Boolean(string='Excluido de IHSS', related='employee_id.ihss_excluded', readonly=True)
    rap_excluded = fields.Boolean(string='Excluido de RAP', related='employee_id.rap_excluded', readonly=True)
    isr_excluded = fields.Boolean(string='Excluido de ISR', related='employee_id.isr_excluded', readonly=True)
    
    # ISR deductions for this version
    isr_employee_deduction_ids = fields.One2many('l10n.hn.isr.employee_deduction', 'version_id',
                                                  string='Deducciones ISR',
                                                  help='Deducciones ISR asociadas a esta versión del contrato',
                                                  domain="[('employee_id', '=', employee_id)]")
    
    # Computed fields for deduction status
    has_ihss = fields.Boolean(string='Tiene IHSS', compute='_compute_deduction_status', store=False)
    has_rap = fields.Boolean(string='Tiene RAP', compute='_compute_deduction_status', store=False)
    has_isr = fields.Boolean(string='Tiene ISR', compute='_compute_deduction_status', store=False)
    
    # IHSS amounts (computed from settings and employee wage)
    ihss_settings_id = fields.Many2one('l10n.hn.ihss.settings', string='Configuración IHSS',
                                        compute='_compute_deduction_status', store=False)
    ihss_amount_monthly = fields.Float(string='Monto IHSS Mensual', digits=(12, 2),
                                        compute='_compute_deduction_status', store=False,
                                        help='Monto mensual de IHSS basado en el salario y configuración')
    ihss_amount_biweekly = fields.Float(string='Monto IHSS Quincenal', digits=(12, 2),
                                         compute='_compute_deduction_status', store=False,
                                         help='Monto quincenal de IHSS')
    ihss_ivm_amount = fields.Float(string='IVM Mensual', digits=(12, 2),
                                    compute='_compute_deduction_status', store=False)
    ihss_em_amount = fields.Float(string='ENF-MAT Mensual', digits=(12, 2),
                                   compute='_compute_deduction_status', store=False)
    ihss_manual = fields.Boolean(string='IHSS Manual', default=False,
                                 help='Sobrescribir con monto manual de IHSS')
    amount_ihss_manual = fields.Float(string='Monto IHSS Manual', digits=(12, 2),
                                      help='Monto IHSS manual por período cuando ihss_manual está activo')
    
    # RAP amounts (computed from settings and employee wage)
    rap_settings_id = fields.Many2one('l10n.hn.rap.settings', string='Configuración RAP',
                                       compute='_compute_deduction_status', store=False)
    rap_foviif_amount_monthly = fields.Float(string='RAP Mensual', digits=(12, 2),
                                             compute='_compute_deduction_status', store=False,
                                             help='Monto mensual de RAP basado en el salario')
    rap_foviif_amount_biweekly = fields.Float(string='RAP Quincenal', digits=(12, 2),
                                               compute='_compute_deduction_status', store=False)
    
    # ISR information
    isr_config_id = fields.Many2one('l10n.hn.isr.config', string='Configuración ISR',
                                     compute='_compute_deduction_status', store=False)
    
    # ISR annual income and deductions fields (for SAR 2026 calculation)
    dias_vacaciones_pagadas_anual = fields.Integer(string='Días Vacaciones Pagadas Anual',
                                                   help='Días de vacaciones pagadas en el año fiscal')
    colegiacion_anual = fields.Float(string='Colegiación Profesional Anual', digits=(12, 2),
                                     help='Colegiación profesional anual para deducción ISR')
    pension_privada_anual = fields.Float(string='Pensión Previsión Privada Anual', digits=(12, 2),
                                         help='Pensiones de previsión privada anuales para deducción ISR')
    otros_ingresos_anual = fields.Float(string='Otros Ingresos Anuales', digits=(12, 2),
                                        help='Otros ingresos anuales gravables')
    amount_other_income = fields.Float(string='Otros Ingresos Período', digits=(12, 2), default=0.0,
                                       help='Turnos extra u otros ingresos del período actual (desde planilla)')

    # Historial de horas extra desde planillas
    extra_hour_ids = fields.One2many('l10n.hn.extra.hours.register', 'version_id',
                                     string='Registros Horas Extra', readonly=True)
    otras_deducciones_anual = fields.Float(string='Otras Deducciones Anuales', digits=(12, 2),
                                           help='Otras deducciones anuales para ISR')
    isr_retenido_ytd = fields.Float(string='ISR Retenido YTD', digits=(12, 2), default=0.0,
                                    help='ISR retenido acumulado desde inicio del año fiscal (se actualiza al cerrar nómina)')
    amount_isr_calculated = fields.Float(
        string='ISR Calculado por Período',
        digits=(12, 2),
        default=0.0,
        help='Monto ISR por período calculado automáticamente por el proceso "Establecer ISR".',
    )
    isr_manual = fields.Boolean(
        string='ISR Manual',
        default=False,
        help='Activar para sobreescribir manualmente el ISR calculado.',
    )
    amount_isr_manual = fields.Float(
        string='Monto ISR Manual',
        digits=(12, 2),
        help='Monto ISR por período cuando se activa la sobreescritura manual.',
    )

    # RAP fields set by "Establecer RAP" flow
    rap_setup_id = fields.Many2one('hr.rap', string='Configuración RAP Asignada',
                                   help='Configuración RAP asignada por el flujo Establecer RAP')
    rap_fee = fields.Float(string='Cuota RAP', digits=(12, 2),
                           help='Cuota RAP por período asignada por Establecer RAP')
    rap_manual = fields.Boolean(string='RAP Manual', default=False,
                                help='Sobrescribir con monto manual de RAP')
    amount_rap_manual = fields.Float(string='Monto RAP Manual', digits=(12, 2),
                                     help='Monto RAP manual por período cuando rap_manual está activo')

    def _get_auto_name_for_version(self):
        """Generar nombre automático para versión de contrato: Empleado - Cargo - Fecha."""
        self.ensure_one()
        if not self.employee_id:
            return False
        parts = [self.employee_id.name or '']
        if self.job_id:
            parts.append(self.job_id.name or '')
        dt = self.contract_date_start or self.date_version or fields.Date.today()
        parts.append(str(dt))
        return ' - '.join(p for p in parts if p)

    def _compute_auto_name_from_vals(self, vals):
        """Generar nombre desde dict de vals (para create)."""
        employee_id = vals.get('employee_id')
        if not employee_id:
            return False
        employee = self.env['hr.employee'].browse(employee_id)
        if not employee.exists():
            return False
        parts = [employee.name or '']
        job_id = vals.get('job_id')
        if job_id:
            job = self.env['hr.job'].browse(job_id)
            if job.exists():
                parts.append(job.name or '')
        dt = vals.get('contract_date_start') or vals.get('date_version') or fields.Date.today()
        parts.append(str(dt))
        return ' - '.join(p for p in parts if p)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('employee_id') and not vals.get('name'):
                vals['name'] = self._compute_auto_name_from_vals(vals) or ''
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        # Si es versión con empleado y name quedó vacío, generar y persistir
        to_fix = self.filtered(lambda v: v.employee_id and not v.name)
        if to_fix and not self.env.context.get('_auto_naming_version'):
            for version in to_fix:
                auto_name = version._get_auto_name_for_version() or ''
                if auto_name:
                    version.with_context(_auto_naming_version=True).write({'name': auto_name})
        return res

    @api.depends('employee_id', 'employee_id.ihss_excluded', 'employee_id.rap_excluded', 'employee_id.isr_excluded',
                 'employee_id.company_id', 'wage', 'periodicity')
    def _compute_deduction_status(self):
        """Compute deduction status and amounts based on employee configuration and company settings"""
        for version in self:
            employee = version.employee_id
            if not employee:
                version.has_ihss = False
                version.has_rap = False
                version.has_isr = False
                version.ihss_settings_id = False
                version.rap_settings_id = False
                version.isr_config_id = False
                version.ihss_amount_monthly = 0.0
                version.ihss_amount_biweekly = 0.0
                version.ihss_ivm_amount = 0.0
                version.ihss_em_amount = 0.0
                version.rap_foviif_amount_monthly = 0.0
                version.rap_foviif_amount_biweekly = 0.0
                continue
            
            # IHSS Calculation
            ihss_settings = employee.ihss_settings_id
            version.ihss_settings_id = ihss_settings.id if ihss_settings else False
            
            if not employee.ihss_excluded and ihss_settings:
                version.has_ihss = True
                # Calculate IHSS based on wage and ceiling
                wage = version.wage or 0.0
                
                # IVM calculation (based on ceiling)
                ivm_base = min(wage, ihss_settings.ivm_ceiling_monthly)
                version.ihss_ivm_amount = round(ivm_base * (ihss_settings.ivm_employee_rate / 100.0), 2)
                
                # EM calculation (based on ceiling)
                em_base = min(wage, ihss_settings.em_ceiling_monthly)
                version.ihss_em_amount = round(em_base * (ihss_settings.em_employee_rate / 100.0), 2)
                
                # Total monthly IHSS
                version.ihss_amount_monthly = version.ihss_ivm_amount + version.ihss_em_amount
                
                # Biweekly amount (half of monthly)
                version.ihss_amount_biweekly = round(version.ihss_amount_monthly / 2.0, 2)
            else:
                version.has_ihss = False
                version.ihss_amount_monthly = 0.0
                version.ihss_amount_biweekly = 0.0
                version.ihss_ivm_amount = 0.0
                version.ihss_em_amount = 0.0
            
            # RAP Calculation
            rap_settings = employee.rap_settings_id
            version.rap_settings_id = rap_settings.id if rap_settings else False
            
            if not employee.rap_excluded and rap_settings:
                version.has_rap = True
                # Calculate RAP FOVIIF based on wage and floor
                wage = version.wage or 0.0
                
                # FOVIIF applies only if wage exceeds IVM ceiling (from IHSS settings)
                ivm_ceiling = ihss_settings.ivm_ceiling_monthly if ihss_settings else 0.0
                if wage > ivm_ceiling:
                    # FOVIIF base is the excess over IVM ceiling, but capped at FOVIIF floor
                    foviif_base = max(0.0, min(wage - ivm_ceiling, rap_settings.foviif_floor_monthly))
                    version.rap_foviif_amount_monthly = round(foviif_base * (rap_settings.foviif_employee_rate / 100.0), 2)
                    version.rap_foviif_amount_biweekly = round(version.rap_foviif_amount_monthly / 2.0, 2)
                else:
                    version.rap_foviif_amount_monthly = 0.0
                    version.rap_foviif_amount_biweekly = 0.0
            else:
                version.has_rap = False
                version.rap_foviif_amount_monthly = 0.0
                version.rap_foviif_amount_biweekly = 0.0
            
            # ISR Check
            isr_config = self.env['l10n.hn.isr.config'].search([
                ('company_id', '=', employee.company_id.id),
                ('year', '=', fields.Date.today().year),
                ('state', '=', 'validated')
            ], limit=1)
            version.isr_config_id = isr_config.id if isr_config else False
            version.has_isr = not employee.isr_excluded and bool(isr_config)
    
    def _get_leave_work_entry_type_dates(self, leave, date_from, date_to, employee):
        """
        Incapacidad IHSS (Honduras) - DÍAS CALENDARIO:
        Odoo solo crea work entries en fechas con jornada laboral (attendances).
        El tipo (Patrono vs IHSS) se decide por case_day_index del día calendario:
        - Días 1-3 calendario => Patrono (HN_INCAP_PAT)
        - Días >= 4 calendario => IHSS (HN_INCAP_IHSS)
        Ejemplo: incapacidad Vie 5 días => Vie(1)Pat, Sáb(2)Pat, Dom(3)Pat, Lun(4)IHSS, Mar(5)IHSS.
        El Lunes genera work entry tipo IHSS aunque sea el 2do día laboral perdido.
        """
        if leave.holiday_id and leave.holiday_id.holiday_status_id.is_ihss_incapacity:
            hr_leave = leave.holiday_id
            # Fecha del intervalo en timezone del empleado/calendario
            tz_name = (self.resource_calendar_id and self.resource_calendar_id.tz) or employee.tz or 'UTC'
            tz = pytz.timezone(tz_name)
            if date_from.tzinfo:
                interval_date = date_from.astimezone(tz).date()
            else:
                interval_date = pytz.utc.localize(date_from).astimezone(tz).date()

            case_day_index = hr_leave.get_case_day_index_for_date(interval_date)
            if case_day_index <= 0:
                return super()._get_leave_work_entry_type_dates(leave, date_from, date_to, employee)

            if case_day_index <= 3:
                return self.env.ref('l10n_hn_hr_payroll.work_entry_type_hn_incap_pat')
            return self.env.ref('l10n_hn_hr_payroll.work_entry_type_hn_incap_ihss')

        return super()._get_leave_work_entry_type_dates(leave, date_from, date_to, employee)

    _SCHEDULE_TO_PERIODICITY = {
        'weekly': 'weekly',
        'bi-weekly': 'biweekly',
        'biweekly': 'biweekly',
        'monthly': 'monthly',
    }
    _PERIODICITY_TO_SCHEDULE = {
        'weekly': 'weekly',
        'biweekly': 'bi-weekly',
        'monthly': 'monthly',
    }

    @api.depends('structure_type_id', 'structure_type_id.default_schedule_pay')
    def _compute_periodicity(self):
        """Compute periodicity from structure_type_id (source of truth, no circular dep)"""
        for version in self:
            if version.structure_type_id and version.structure_type_id.default_schedule_pay:
                version.periodicity = self._SCHEDULE_TO_PERIODICITY.get(
                    version.structure_type_id.default_schedule_pay, 'monthly'
                )
            elif not version.periodicity:
                version.periodicity = 'monthly'

    @api.depends('periodicity')
    def _compute_schedule_pay(self):
        """Derive schedule_pay from periodicity (no circular dependency)"""
        for version in self:
            if version.periodicity and version.periodicity in self._PERIODICITY_TO_SCHEDULE:
                version.schedule_pay = self._PERIODICITY_TO_SCHEDULE[version.periodicity]
            elif version.structure_type_id and version.structure_type_id.default_schedule_pay:
                version.schedule_pay = version.structure_type_id.default_schedule_pay
            else:
                version.schedule_pay = 'monthly'

    def _find_available_date_version(self, employee_id, date_obj, exclude_id=False):
        """Find an available date_version for an employee, avoiding conflicts."""
        domain = [('employee_id', '=', employee_id), ('date_version', '=', date_obj)]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))
        if not self.search_count(domain):
            return date_obj
        for offset in [timedelta(days=-1), timedelta(days=1)]:
            candidate = date_obj + offset
            d = [('employee_id', '=', employee_id), ('date_version', '=', candidate)]
            if exclude_id:
                d.append(('id', '!=', exclude_id))
            if not self.search_count(d):
                return candidate
        for i in range(2, 31):
            candidate = date_obj - timedelta(days=i)
            d = [('employee_id', '=', employee_id), ('date_version', '=', candidate)]
            if exclude_id:
                d.append(('id', '!=', exclude_id))
            if not self.search_count(d):
                return candidate
        raise ValidationError(_(
            'No se encontró una fecha disponible para la versión del empleado. '
            'Por favor, seleccione una fecha diferente.'
        ))

    @api.model_create_multi
    def create(self, vals_list):
        """Sync periodicity with schedule_pay when creating versions"""
        for vals in vals_list:
            # If periodicity is not provided, compute it from structure_type_id
            if 'periodicity' not in vals and 'structure_type_id' in vals:
                structure_type = self.env['hr.payroll.structure.type'].browse(vals['structure_type_id'])
                if structure_type and structure_type.default_schedule_pay:
                    schedule_to_periodicity = {
                        'weekly': 'weekly',
                        'bi-weekly': 'biweekly',
                        'biweekly': 'biweekly',
                        'monthly': 'monthly',
                    }
                    vals['periodicity'] = schedule_to_periodicity.get(structure_type.default_schedule_pay, 'monthly')
            elif 'periodicity' not in vals:
                # Default to monthly if no structure type
                vals['periodicity'] = 'monthly'
            
            # Sync schedule_pay with periodicity
            if 'periodicity' in vals and 'schedule_pay' not in vals:
                # Map our periodicity to Odoo's schedule_pay format
                periodicity_map = {
                    'weekly': 'weekly',
                    'biweekly': 'bi-weekly',  # Note: Odoo uses 'bi-weekly' with hyphen
                    'monthly': 'monthly',
                }
                if vals['periodicity'] in periodicity_map:
                    vals['schedule_pay'] = periodicity_map[vals['periodicity']]
            
            if 'employee_id' in vals and 'date_version' in vals:
                date_obj = fields.Date.from_string(vals['date_version']) if isinstance(vals['date_version'], str) else vals['date_version']
                vals['date_version'] = self._find_available_date_version(vals['employee_id'], date_obj)

        versions = super().create(vals_list)
        
        for version in versions:
            version._create_default_deductions()
            version._auto_add_to_isr_table()
        
        return versions
    
    def write(self, vals):
        """Sync periodicity with schedule_pay when updating versions"""
        # Prevent direct wage changes unless from salary increase, initial setup, or no payslips
        if 'wage' in vals and not self.env.context.get('from_salary_increase'):
            for version in self:
                if (version.wage or 0) == 0:
                    continue
                if vals.get('wage') == version.wage:
                    continue
                if not version.payslips_count:
                    continue
                raise ValidationError(_('El salario no puede modificarse directamente porque ya existen nóminas asociadas. '
                                      'Debe utilizar el proceso de "Aumentos Salariales" para modificar el salario.'))
        
        if 'date_version' in vals and not self.env.context.get('skip_date_version_check'):
            if len(self) == 1:
                version = self[0]
                employee_id = vals.get('employee_id', version.employee_id.id)
                new_dv = vals['date_version']
                if version.date_version == new_dv:
                    vals.pop('date_version', None)
                else:
                    date_obj = fields.Date.from_string(new_dv) if isinstance(new_dv, str) else new_dv
                    vals['date_version'] = self._find_available_date_version(employee_id, date_obj, exclude_id=version.id)
            else:
                for version in self:
                    emp_id = vals.get('employee_id', version.employee_id.id)
                    new_dv = vals['date_version']
                    if version.date_version == new_dv:
                        continue
                    date_obj = fields.Date.from_string(new_dv) if isinstance(new_dv, str) else new_dv
                    resolved = self._find_available_date_version(emp_id, date_obj, exclude_id=version.id)
                    version.with_context(skip_date_version_check=True).write({'date_version': resolved})
                vals.pop('date_version', None)
        
        # If structure_type_id changes, recompute periodicity and schedule_pay
        if 'structure_type_id' in vals:
            structure_type = self.env['hr.payroll.structure.type'].browse(vals['structure_type_id'])
            if structure_type and structure_type.default_schedule_pay:
                schedule_to_periodicity = {
                    'weekly': 'weekly',
                    'bi-weekly': 'biweekly',
                    'biweekly': 'biweekly',
                    'monthly': 'monthly',
                }
                periodicity_map = {
                    'weekly': 'weekly',
                    'biweekly': 'bi-weekly',
                    'monthly': 'monthly',
                }
                schedule_pay = structure_type.default_schedule_pay
                if 'periodicity' not in vals:
                    vals['periodicity'] = schedule_to_periodicity.get(schedule_pay, 'monthly')
                if 'schedule_pay' not in vals:
                    vals['schedule_pay'] = schedule_pay
        
        if 'periodicity' in vals and 'schedule_pay' not in vals:
            # Map our periodicity to Odoo's schedule_pay format
            periodicity_map = {
                'weekly': 'weekly',
                'biweekly': 'bi-weekly',  # Note: Odoo uses 'bi-weekly' with hyphen
                'monthly': 'monthly',
            }
            if vals['periodicity'] in periodicity_map:
                vals['schedule_pay'] = periodicity_map[vals['periodicity']]
        
        if 'schedule_pay' in vals and 'periodicity' not in vals:
            # Map schedule_pay to periodicity
            schedule_to_periodicity = {
                'weekly': 'weekly',
                'bi-weekly': 'biweekly',
                'biweekly': 'biweekly',
                'monthly': 'monthly',
            }
            if vals['schedule_pay'] in schedule_to_periodicity:
                vals['periodicity'] = schedule_to_periodicity[vals['schedule_pay']]
        
        result = super().write(vals)
        
        if 'employee_id' in vals:
            for version in self:
                version._create_default_deductions()
        
        if 'wage' in vals:
            for version in self:
                version._auto_add_to_isr_table()
        
        return result

    def _create_default_deductions(self):
        """Create default ISR deductions for this version if they don't exist"""
        self.ensure_one()
        if not self.employee_id:
            return
        
        employee = self.employee_id
        
        # Only create if employee is not excluded from ISR
        if employee.isr_excluded:
            return
        
        # Get version start year
        version_year = self.contract_date_start.year if self.contract_date_start else fields.Date.today().year
        
        # Check if ISR config exists for this company and year
        isr_config = self.env['l10n.hn.isr.config'].search([
            ('company_id', '=', employee.company_id.id),
            ('year', '=', version_year),
            ('state', '=', 'validated')
        ], limit=1)
        
        if not isr_config:
            return
        
        # Check if deductions already exist for this version
        existing_deductions = self.isr_employee_deduction_ids.filtered(
            lambda d: d.year == version_year
        )
        
        if existing_deductions:
            # Update version_id for existing deductions if not set
            existing_deductions.write({'version_id': self.id})
            return
        
        # Link any existing employee deductions to this version
        employee_deductions = self.env['l10n.hn.isr.employee_deduction'].search([
            ('employee_id', '=', employee.id),
            ('year', '=', version_year),
            ('version_id', '=', False),
            ('active', '=', True)
        ])
        
        if employee_deductions:
            employee_deductions.write({'version_id': self.id})
        
        # Also check if there are deductions for the employee that should be linked
        # This handles the case where deductions exist but weren't linked to a version
        all_employee_deductions = self.env['l10n.hn.isr.employee_deduction'].search([
            ('employee_id', '=', employee.id),
            ('version_id', '=', False),
            ('active', '=', True)
        ])
        
        # Link deductions that are active during this version's period
        if self.contract_date_start:
            for deduction in all_employee_deductions:
                # Check if deduction period overlaps with version period
                deduction_start = deduction.date_start or date.min
                deduction_end = deduction.date_end or date.max
                version_start = self.contract_date_start
                version_end = self.contract_date_end or date.max
                
                # Check overlap
                if deduction_start <= version_end and deduction_end >= version_start:
                    deduction.write({'version_id': self.id})
    
    def _auto_add_to_isr_table(self):
        """Al crear/modificar una versión, agregar al empleado en la tabla Establecer ISR
        si aplica (salario > exento) y existe un registro ISR del año en borrador."""
        self.ensure_one()
        employee = self.employee_id
        if not employee or employee.isr_excluded or not self.wage:
            return

        year = self.contract_date_start.year if self.contract_date_start else fields.Date.today().year

        isr_parent = self.env['hr.isr.employee'].search([
            ('name', '=', str(year)),
        ], order='state asc', limit=1)
        if not isr_parent:
            return

        exempt = isr_parent.exempt_salary or 0
        if self.wage <= exempt:
            return

        existing = self.env['hr.isr.employee.detail'].search([
            ('parent_id', '=', isr_parent.id),
            ('employee_id', '=', employee.id),
        ], limit=1)
        if existing:
            if existing.version_id != self:
                existing.write({
                    'version_id': self.id,
                    'wage': self.wage,
                })
                existing._recompute_all()
            return

        months_remaining = 12
        if isr_parent.start_date and isr_parent.end_date:
            months_remaining = isr_parent.end_date.month - isr_parent.start_date.month + 1
        elif self.contract_date_start:
            months_remaining = 12 - self.contract_date_start.month + 1

        medical_default = (isr_parent.isr_id.medical_expense or 40000.0) if isr_parent.isr_id else 40000.0
        other_entries = self.otros_ingresos_anual or 0

        rap_annual = 0.0
        if not employee.rap_excluded:
            if self.rap_fee:
                rap_annual = round(self.rap_fee * 24, 2)
            else:
                ihss_settings = self.env['l10n.hn.ihss.settings'].search(
                    [('state', '=', 'validated')], limit=1)
                rap_settings = self.env['l10n.hn.rap.settings'].search(
                    [('state', '=', 'validated')], limit=1)
                if ihss_settings and rap_settings:
                    ivm_ceiling = ihss_settings.ivm_ceiling_monthly
                    rap_rate = rap_settings.foviif_employee_rate / 100.0
                    if self.wage > ivm_ceiling:
                        rap_annual = round((self.wage - ivm_ceiling) * rap_rate * 12, 2)

        detail = self.env['hr.isr.employee.detail'].create({
            'wage': self.wage,
            'employee_id': employee.id,
            'version_id': self.id,
            'parent_id': isr_parent.id,
            'medical_expense': medical_default,
            'total_incomes': (self.wage or 0) * months_remaining + other_entries,
            'amount_rap': rap_annual,
            'amount_ivm': isr_parent.isr_id.amount_ivm if isr_parent.isr_id else 0,
            'amount_membership': self.colegiacion_anual or 0,
            'other_expenses': self.otras_deducciones_anual or 0,
            'other_entries': other_entries,
        })

        if isr_parent.pay_number > 0:
            isr_parent.calculate_isr_one_line(detail)
            if detail.isr_fee:
                self.amount_isr_calculated = detail.isr_fee

    @api.model
    def _auto_link_deductions_to_versions(self):
        """Auto-link existing employee deductions to their versions"""
        # Find all deductions without version_id
        deductions = self.env['l10n.hn.isr.employee_deduction'].search([
            ('version_id', '=', False),
            ('active', '=', True)
        ])
        
        for deduction in deductions:
            employee = deduction.employee_id
            if not employee:
                continue
            
            # Find version that overlaps with deduction period
            deduction_start = deduction.date_start or date.min
            deduction_end = deduction.date_end or date.max
            
            version = self.env['hr.version'].search([
                ('employee_id', '=', employee.id),
                ('contract_date_start', '<=', deduction_end),
                '|',
                ('contract_date_end', '=', False),
                ('contract_date_end', '>=', deduction_start)
            ], order='contract_date_start desc', limit=1)
            
            if version:
                deduction.write({'version_id': version.id})
