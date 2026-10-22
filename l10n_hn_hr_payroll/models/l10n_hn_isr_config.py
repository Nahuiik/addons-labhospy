# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

import logging

_logger = logging.getLogger(__name__)

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime
from dateutil.relativedelta import relativedelta


class L10nHnIsrConfig(models.Model):
    """ISR Configuration - Complete ISR settings with withholding calculation"""
    _name = 'l10n.hn.isr.config'
    _description = 'ISR Configuration'
    _order = 'year desc, company_id'
    _rec_name = 'name'

    _BONUS_CODES = [
        'ALW', 'BONIFICACIONES', 'HOR_EXT', 'COMISIONES', 'INCENTIVOS',
        'BONO_TRANS', 'BONO_ALIM', 'BONO_ESCOLAR', 'BONO_PROD', 'TURNOS_EXT',
    ]

    name = fields.Char(string='Name', compute='_compute_name', store=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company, index=True)
    year = fields.Integer(string='Year', required=True,
                        default=lambda self: fields.Date.today().year, index=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('validated', 'Validated'),
    ], string='State', default='draft', required=True, index=True)
    
    # Periodicity configuration
    periodicity = fields.Selection([
        ('monthly', 'Monthly'),
        ('biweekly', 'Biweekly'),
    ], string='Payment Periodicity', required=True, default='biweekly')
    apply_in = fields.Selection([
        ('first_half', 'First Half (1-15)'),
        ('second_half', 'Second Half (16-end)'),
        ('both', 'Both Halves'),
    ], string='Apply In', default='both',
       help='For biweekly: when to apply ISR withholding')
    
    # Salary minimum for 13th/14th month exemption
    salario_minimo_promedio = fields.Float(string='Salario Mínimo Promedio Mensual', 
                                           required=True, digits=(12, 2),
                                           help='Salario mínimo promedio mensual usado para calcular exención de 13vo y 14to mes (10x este monto)')
    
    # Salario exento mensual (umbral bajo el cual no se retiene ISR)
    salario_exento = fields.Float(string='Salario Exento Mensual', digits=(12, 2),
                                  help='Salario mensual exento: si wage <= este monto, no se retiene ISR. Si está vacío, se usa el umbral del primer tramo.')
    
    # SAR 2026 fields for exemption cap calculation
    multiplicador_tope_exento_decimos = fields.Float(string='Multiplicador Tope Exento Décimos', 
                                                     digits=(12, 2), default=10.0,
                                                     help='Multiplicador para calcular el tope exento de décimos (por defecto 10)')
    tope_exento_decimos = fields.Float(string='Tope Exento Décimos', 
                                       compute='_compute_tope_exento_decimos', 
                                       digits=(12, 2),
                                       help='Tope exento para décimos 13 y 14 (salario_minimo_promedio × multiplicador)')
    
    # SAR 2026 fields for withholding calculation
    meses_retencion = fields.Integer(string='Meses de Retención', default=12,
                                     help='Número de meses en los que se aplica la retención ISR durante el año')
    meses_excluidos_retencion = fields.Char(string='Meses Excluidos de Retención', 
                                            help='Meses excluidos de retención separados por comas (ej: 6,12 para junio y diciembre)')
    
    # SAR 2026 fields for third age exemption
    edad_tercera_edad = fields.Integer(string='Edad Tercera Edad', default=65,
                                      help='Edad mínima para aplicar exoneración de tercera edad')
    exoneracion_tercera_edad_monto = fields.Float(string='Exoneración Tercera Edad (Monto)', 
                                                  digits=(12, 2), default=350000.0,
                                                  help='Monto de exoneración para empleados de tercera edad')
    
    # Tax table (one2many)
    bracket_ids = fields.One2many('l10n.hn.isr.config.bracket', 'config_id', 
                                  string='Tax Brackets', required=True)
    
    # Deductible rules/inputs (many2many to salary rules or input types)
    deductible_rule_ids = fields.Many2many('hr.salary.rule', 
                                          'isr_config_deductible_rule_rel',
                                          'config_id', 'rule_id',
                                          string='Deductible Salary Rules',
                                          help='Salary rules that reduce taxable income (e.g., AFP, Colegio Profesional)')
    deductible_input_type_ids = fields.Many2many('hr.payslip.input.type',
                                                'isr_config_deductible_input_rel',
                                                'config_id', 'input_type_id',
                                                string='Deductible Input Types',
                                                help='Payslip input types that reduce taxable income')
    
    # Medical expenses deduction configuration
    medical_expenses_enabled = fields.Boolean(string='Enable Medical Expenses Deduction', default=False)
    medical_expenses_by_age = fields.Boolean(string='Medical Expenses by Age', default=False,
                                            help='Apply different medical expense limits by employee age')
    medical_expenses_default_limit = fields.Float(string='Default Medical Expenses Limit', 
                                                  digits=(12, 2), default=40000.0,
                                                  help='Default annual limit for medical expenses deduction')
    medical_expenses_age_rules = fields.One2many('l10n.hn.isr.medical_expense_rule', 'config_id',
                                                 string='Medical Expenses by Age Rules')
    
    active = fields.Boolean(string='Active', default=True)

    def action_calculate_isr_review(self):
        """Open wizard to pre-calculate ISR for all employees"""
        self.ensure_one()
        if self.state != 'validated':
            raise UserError(_('La configuración debe estar validada para calcular ISR.'))
        return {
            'name': _('Calcular ISR para Revisión'),
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.hn.isr.calculation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_config_id': self.id,
            },
        }
    
    @api.depends('salario_minimo_promedio', 'multiplicador_tope_exento_decimos')
    def _compute_tope_exento_decimos(self):
        """Compute exemption cap for 13th and 14th month"""
        for rec in self:
            rec.tope_exento_decimos = rec.salario_minimo_promedio * rec.multiplicador_tope_exento_decimos
    
    @api.depends('year', 'company_id')
    def _compute_name(self):
        """Generate config name"""
        for rec in self:
            rec.name = f'ISR Config {rec.year} - {rec.company_id.name or "All Companies"}'
    
    @api.constrains('year', 'company_id', 'state')
    def _check_unique_validated(self):
        """Only one validated config per year and company"""
        validated = self.filtered(lambda r: r.state == 'validated')
        if not validated:
            return
        for rec in validated:
            if self.search_count([
                ('year', '=', rec.year),
                ('company_id', '=', rec.company_id.id),
                ('state', '=', 'validated'),
                ('id', '!=', rec.id),
            ]):
                raise ValidationError(_(
                    'There can only be one validated ISR configuration per year and company.'
                ))
    
    def action_validate(self):
        """Validate ISR configuration"""
        self.ensure_one()
        if not self.bracket_ids:
            raise ValidationError(_('ISR configuration must have at least one tax bracket.'))
        self.write({'state': 'validated'})
        return True
    
    def action_draft(self):
        """Set to draft"""
        self.ensure_one()
        self.write({'state': 'draft'})
        return True
    
    def calculate_isr_annual(self, taxable_amount):
        """Calculate annual ISR based on tax brackets"""
        self.ensure_one()
        if taxable_amount <= 0:
            return 0.0
        
        # Find applicable bracket
        applicable_bracket = False
        for bracket in self.bracket_ids.sorted(key='from_amount', reverse=True):
            if taxable_amount >= bracket.from_amount:
                applicable_bracket = bracket
                break
        
        if not applicable_bracket:
            return 0.0
        
        # Calculate tax: fixed_quota + (excess_over * rate / 100)
        excess = taxable_amount - applicable_bracket.excess_over
        tax = applicable_bracket.fixed_quota + (excess * applicable_bracket.rate / 100.0)
        
        return round(tax, 2)
    
    def _get_exempt_monthly_threshold(self):
        """Obtener umbral mensual exento (primer tramo con tasa 0)."""
        self.ensure_one()
        exempt_bracket = self.bracket_ids.filtered(lambda b: b.rate == 0).sorted(key='from_amount')
        if exempt_bracket:
            return exempt_bracket[0].to_amount / 12.0
        return 0.0

    def get_medical_expense_limit(self, employee_age=None):
        """Get medical expense deduction limit for an employee"""
        self.ensure_one()
        if not self.medical_expenses_enabled:
            return 0.0
        
        if self.medical_expenses_by_age and employee_age is not None:
            # Find applicable age rule
            for rule in self.medical_expenses_age_rules.sorted(key='age_from', reverse=True):
                if employee_age >= rule.age_from and (not rule.age_to or employee_age <= rule.age_to):
                    return rule.limit_amount
            # Default if no rule matches
            return self.medical_expenses_default_limit
        
        return self.medical_expenses_default_limit
    
    @api.model
    def compute_withholding(self, payslip):
        """Calculate ISR withholding for a payslip
        
        This is the main method that implements the ISR withholding algorithm.
        It uses SAR 2026 algorithm if config has new fields, otherwise uses legacy algorithm.
        
        Returns: dict with calculation details and period_amount
        """
        if not payslip or not payslip.employee_id:
            return {'period_amount': 0.0, 'audit_data': {}}
        
        employee = payslip.employee_id
        
        version = employee.current_version_id.sudo() if employee.current_version_id else False

        # 1) Override manual del usuario (máxima prioridad)
        if version and version.isr_manual and version.amount_isr_manual:
            return {'period_amount': -abs(version.amount_isr_manual), 'audit_data': {'manual': True}}

        # 2) ISR calculado por "Establecer ISR" (si existe)
        if version and version.amount_isr_calculated:
            return {'period_amount': -abs(version.amount_isr_calculated), 'audit_data': {'calculated': True}}
        
        # Check if employee is exempt
        if employee.isr_excluded:
            return {'period_amount': 0.0, 'audit_data': {'exempt': True}}
        
        # Get ISR config for the year
        year = payslip.date_to.year if payslip.date_to else fields.Date.today().year
        config = self.env['l10n.hn.isr.config'].search([
            ('year', '=', year),
            ('company_id', '=', payslip.company_id.id),
            ('state', '=', 'validated'),
            ('active', '=', True)
        ], limit=1)
        
        if not config:
            return {'period_amount': 0.0, 'audit_data': {'error': 'No ISR config found'}}
        
        # Salario exento: si wage <= salario exento mensual, no retener ISR
        # Prioridad: config.salario_exento > umbral del primer tramo
        if version and version.wage:
            exempt_monthly = config.salario_exento or config._get_exempt_monthly_threshold()
            if exempt_monthly and version.wage <= exempt_monthly:
                return {'period_amount': 0.0, 'audit_data': {'exempt_by_salary': True}}
        
        # Check if this period applies (for biweekly)
        if config.periodicity == 'biweekly':
            if not config._period_applies(payslip):
                return {'period_amount': 0.0, 'audit_data': {'period_not_applicable': True}}
        
        if config.multiplicador_tope_exento_decimos:
            return config._compute_withholding_sar_2026(payslip)
        return config._compute_withholding_legacy(payslip)
    
    def _compute_withholding_sar_2026(self, payslip):
        """Calcular retención ISR usando algoritmo SAR 2026"""
        self.ensure_one()
        employee = payslip.employee_id
        year = payslip.date_to.year if payslip.date_to else fields.Date.today().year
        
        # Obtener sueldos YTD y proyectar anual
        salary_ytd = self._get_salary_ytd(employee, year, payslip.date_to, exclude_payslip_id=payslip.id)
        projected_salary_annual = self._project_annual_salary(employee, salary_ytd, payslip.date_from)
        
        # Obtener bonos YTD y proyectar anual
        bonuses_ytd = self._get_bonuses_ytd(employee, year, payslip.date_to, exclude_payslip_id=payslip.id)
        projected_bonuses_annual = self._project_annual_bonuses(employee, bonuses_ytd, payslip.date_from)
        
        # Otros ingresos anuales
        version = employee.current_version_id.sudo() if employee.current_version_id else False
        other_income_annual = version.otros_ingresos_anual if version else 0.0
        
        # Calcular retención según SAR 2026
        result = self._calculate_isr_withholding_sar_2026(
            employee,
            payslip.date_from,
            payslip.date_to,
            salary_ytd,
            projected_salary_annual,
            bonuses_ytd,
            projected_bonuses_annual,
            other_income_annual
        )
        
        if 'isr_amount' in payslip._fields:
            payslip.isr_amount = result['retention_current_month']
        if 'isr_base' in payslip._fields:
            payslip.isr_base = result['base_isr_monthly']
        
        # Crear registro de auditoría
        audit_data = {
            'employee_id': employee.id,
            'company_id': payslip.company_id.id,
            'year': year,
            'period_start': payslip.date_from,
            'period_end': payslip.date_to,
            'payslip_id': payslip.id,
            'config_id': self.id,
            'salary_annual': result['salary_annual'],
            'thirteenth_month_taxable': result['excess_13th'],
            'fourteenth_month_taxable': result['excess_14th'],
            'excess_vacations': result['excess_vacations'],
            'total_taxable_income_ytd': result['income_total'],
            'total_deductions_ytd': result['deductions_total'],
            'projected_taxable_base': result['taxable_base'],
            'isr_annual_calculated': result['isr_annual'],
            'isr_retained_ytd': version.isr_retenido_ytd if version else 0.0,
            'isr_period_amount': result['retention_current_month'],
        }
        
        try:
            self.env['l10n.hn.isr.audit'].create(audit_data)
        except Exception:
            _logger.warning(
                "Failed to create ISR audit for employee %s", employee.display_name, exc_info=True
            )
        
        return {
            'period_amount': -result['retention_current_month'],  # Negativo porque es deducción
            'audit_data': audit_data
        }
    
    def _compute_withholding_legacy(self, payslip):
        """Calcular retención ISR usando algoritmo legacy (método original)"""
        self.ensure_one()
        employee = payslip.employee_id
        
        # Get period dates
        period_start = payslip.date_from
        period_end = payslip.date_to
        year = period_end.year if period_end else fields.Date.today().year
        
        # Calculate taxable income YTD (exclude current payslip)
        taxable_income_ytd = self._calculate_taxable_income_ytd(
            employee, year, period_end, payslip.company_id, exclude_payslip_id=payslip.id
        )
        
        # Calculate deductions YTD (exclude current payslip)
        deductions_ytd = self._calculate_deductions_ytd(
            employee, year, period_end, payslip.company_id, self, exclude_payslip_id=payslip.id
        )
        
        # Calculate 13th and 14th month taxable portions
        thirteenth_taxable, fourteenth_taxable = self._calculate_bonus_taxable(
            employee, year, self.salario_minimo_promedio
        )
        
        # Add bonus taxable to YTD
        taxable_income_ytd += thirteenth_taxable + fourteenth_taxable
        
        # Calculate annual projection
        projection_data = self._calculate_annual_projection(
            employee, year, period_end, taxable_income_ytd, deductions_ytd, self
        )
        
        # Calculate annual ISR
        projected_taxable_base = projection_data['projected_income'] - projection_data['projected_deductions']
        isr_annual = self.calculate_isr_annual(max(0, projected_taxable_base))
        
        # Get ISR retained YTD (from previous payslips)
        isr_retained_ytd = self._get_isr_retained_ytd(employee, year, period_end, payslip.id)
        
        # Calculate period withholding
        periods_remaining = projection_data['periods_remaining']
        isr_balance = max(0, isr_annual - isr_retained_ytd)
        
        if periods_remaining > 0:
            period_amount = -round(isr_balance / periods_remaining, 2)
        else:
            period_amount = -round(isr_balance, 2)
        
        # Ensure non-negative
        period_amount = min(0, period_amount)
        
        # Create audit record
        audit_data = {
            'employee_id': employee.id,
            'company_id': payslip.company_id.id,
            'year': year,
            'period_start': period_start,
            'period_end': period_end,
            'payslip_id': payslip.id,
            'config_id': self.id,
            'basic_income_ytd': projection_data.get('basic_income_ytd', 0),
            'variable_income_ytd': projection_data.get('variable_income_ytd', 0),
            'thirteenth_month_taxable': thirteenth_taxable,
            'fourteenth_month_taxable': fourteenth_taxable,
            'total_taxable_income_ytd': taxable_income_ytd,
            'payroll_deductions_ytd': deductions_ytd.get('payroll', 0),
            'employee_declared_deductions_ytd': deductions_ytd.get('declared', 0),
            'medical_expenses_ytd': deductions_ytd.get('medical', 0),
            'total_deductions_ytd': deductions_ytd.get('total', 0),
            'projected_annual_income': projection_data['projected_income'],
            'projected_annual_deductions': projection_data['projected_deductions'],
            'projected_taxable_base': projected_taxable_base,
            'isr_annual_calculated': isr_annual,
            'isr_retained_ytd': isr_retained_ytd,
            'isr_balance': isr_balance,
            'isr_period_amount': abs(period_amount),
            'periods_remaining': periods_remaining,
        }
        
        # Create audit record
        self.env['l10n.hn.isr.audit'].create(audit_data)
        
        return {
            'period_amount': period_amount,
            'audit_data': audit_data
        }
    
    def _calculate_isr_withholding_sar_2026(self, employee, payslip_date_from, payslip_date_to,
                                            salary_ytd, projected_salary_annual,
                                            bonuses_ytd, projected_bonuses_annual,
                                            other_income_annual=0.0):
        """
        Calcular ISR según plantilla SAR 2026
        
        Args:
            employee: hr.employee record
            payslip_date_from: fecha inicio del período de nómina
            payslip_date_to: fecha fin del período de nómina
            salary_ytd: sueldo acumulado YTD
            projected_salary_annual: sueldo anual proyectado (R)
            bonuses_ytd: bonos acumulados YTD
            projected_bonuses_annual: bonos anuales proyectados
            other_income_annual: otros ingresos anuales
        
        Returns:
            dict con:
            - isr_annual: ISR anual proyectado
            - retention_current_month: Retención del mes actual
            - base_isr_monthly: Base ISR mensual (AH / meses_retencion)
            - taxable_base: Base gravable (AH)
            - deductions_total: Total deducciones (AG)
            - income_total: Total ingresos gravables (AA)
            - salary_annual: Sueldo anual (R)
            - excess_13th: Exceso décimo 13
            - excess_14th: Exceso décimo 14
            - excess_vacations: Exceso vacaciones
        """
        self.ensure_one()
        
        # 1) Sueldo Anual (R)
        R = projected_salary_annual
        
        # 2) Décimos
        decimo_13 = R / 12.0
        decimo_14 = R / 12.0
        tope_exento = self.tope_exento_decimos
        exceso_13 = max(0, decimo_13 - tope_exento)
        exceso_14 = max(0, decimo_14 - tope_exento)
        
        # 3) Vacaciones
        version = employee.current_version_id.sudo() if employee.current_version_id else False
        dias_vacaciones = version.dias_vacaciones_pagadas_anual if version else 0
        if dias_vacaciones > 30:
            exceso_vacaciones = (dias_vacaciones - 30) * (R / 360.0)
        else:
            exceso_vacaciones = 0.0
        
        # 4) Total Ingresos gravables (AA)
        AA = R + exceso_14 + exceso_13 + exceso_vacaciones + projected_bonuses_annual + other_income_annual
        
        # 5) Total Deducciones (AG)
        # Gastos médicos según edad
        edad = self._get_employee_age(employee)
        gastos_medicos = self.get_medical_expense_limit(edad) if self.medical_expenses_enabled else 0.0
        
        # Deducciones: modelo l10n.hn.isr.employee_deduction + versión (se suman ambas fuentes)
        # El empleado puede tener deducciones en el modelo Y valores manuales en la versión
        company_id = employee.company_id.id if employee.company_id else self.env.company.id
        breakdown = self.env['l10n.hn.isr.employee_deduction'].get_annual_deductions_breakdown(
            employee, payslip_date_from.year, company_id
        )
        colegiacion = breakdown['membership'] + (version.colegiacion_anual if version else 0.0)
        pension_privada = breakdown['pension'] + (version.pension_privada_anual if version else 0.0)
        otras_deducciones = breakdown['other'] + (version.otras_deducciones_anual if version else 0.0)
        
        AG = gastos_medicos + colegiacion + pension_privada + otras_deducciones
        
        # 6) Renta neta (AJ) y renta neta gravable (AH)
        AJ = AA - AG
        if edad >= self.edad_tercera_edad:
            AH = max(0, AJ - self.exoneracion_tercera_edad_monto)
        else:
            AH = AJ
        
        if AH <= 0:
            return {
                'isr_annual': 0.0,
                'retention_current_month': 0.0,
                'base_isr_monthly': 0.0,
                'taxable_base': AH,
                'deductions_total': AG,
                'income_total': AA,
                'salary_annual': R,
                'excess_13th': exceso_13,
                'excess_14th': exceso_14,
                'excess_vacations': exceso_vacaciones
            }
        
        # 7) ISR anual por tabla progresiva marginal
        isr_annual = self.calculate_isr_annual(AH)
        
        # 8) Retención mensual
        hire_date = self._get_hire_date_for_year(employee, payslip_date_from.year)
        if hire_date:
            mes_inicio = hire_date.month
            meses_excluidos = self._parse_excluded_months()
            effective_meses_retencion = sum(
                1 for m in range(mes_inicio, 13) if m not in meses_excluidos
            )
        else:
            mes_inicio = 1
            effective_meses_retencion = self.meses_retencion
            meses_excluidos = self._parse_excluded_months()
        
        cuota_mensual_teorica = isr_annual / effective_meses_retencion if effective_meses_retencion > 0 else 0.0
        
        mes_actual = payslip_date_from.month
        if mes_actual in meses_excluidos or (hire_date and mes_actual < mes_inicio):
            retention_current_month = 0.0
        else:
            numero_cuota_actual = self._get_current_installment_number(mes_actual, meses_excluidos, mes_inicio)
            objetivo_acumulado = cuota_mensual_teorica * numero_cuota_actual
            retenido_ytd = version.isr_retenido_ytd if version else 0.0
            retention_current_month = max(0, objetivo_acumulado - retenido_ytd)
        
        base_isr_monthly = AH / effective_meses_retencion if effective_meses_retencion > 0 else 0.0
        
        return {
            'isr_annual': isr_annual,
            'retention_current_month': retention_current_month,
            'base_isr_monthly': base_isr_monthly,
            'taxable_base': AH,
            'deductions_total': AG,
            'income_total': AA,
            'salary_annual': R,
            'excess_13th': exceso_13,
            'excess_14th': exceso_14,
            'excess_vacations': exceso_vacaciones
        }
    
    def _get_employee_age(self, employee):
        """Calcular edad del empleado desde birthday"""
        if not employee.birthday:
            return 0
        
        today = fields.Date.today()
        age = today.year - employee.birthday.year
        if (today.month, today.day) < (employee.birthday.month, employee.birthday.day):
            age -= 1
        return age
    
    def _get_hire_date_for_year(self, employee, year):
        """Fecha de ingreso efectiva para el año. None si ingresó antes del 1 de enero."""
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        versions = self.env['hr.version'].search([
            ('employee_id', '=', employee.id),
            ('contract_date_start', '<=', year_end),
            '|', ('contract_date_end', '=', False), ('contract_date_end', '>=', year_start),
        ], order='contract_date_start asc')
        if not versions:
            return None
        first_start = versions[0].contract_date_start
        if first_start <= year_start:
            return None
        return first_start
    
    def _get_annual_deductions_from_model(self, employee, year):
        """Obtener deducciones anuales desde l10n.hn.isr.employee_deduction"""
        deductions = self.env['l10n.hn.isr.employee_deduction'].search([
            ('employee_id', '=', employee.id),
            ('year', '=', year),
            ('active', '=', True)
        ])
        
        total = 0.0
        for deduction in deductions:
            # Calcular monto anual según periodicidad
            if deduction.periodicity == 'annual':
                total += deduction.amount
            elif deduction.periodicity == 'monthly':
                # Proyectar a anual (asumiendo 12 meses)
                total += deduction.amount * 12
            elif deduction.periodicity == 'per_payslip':
                # Sumar YTD desde payslips
                # Por ahora, usar monto mensual * 12 como aproximación
                total += deduction.amount * 12
        
        return total
    
    def _parse_excluded_months(self):
        """Parsear meses_excluidos_retencion (string "6,12" → [6, 12])"""
        if not self.meses_excluidos_retencion:
            return []
        
        try:
            meses = [int(m.strip()) for m in self.meses_excluidos_retencion.split(',') if m.strip().isdigit()]
            return [m for m in meses if 1 <= m <= 12]
        except (ValueError, TypeError, AttributeError):
            return []
    
    def _get_current_installment_number(self, mes_actual, meses_excluidos, mes_inicio=1):
        """Calcular número de cuota actual (excluyendo meses excluidos).
        mes_inicio: primer mes a considerar (para empleados que ingresan a mitad de año)."""
        numero_cuota = 0
        for mes in range(mes_inicio, mes_actual + 1):
            if mes not in meses_excluidos:
                numero_cuota += 1
        return numero_cuota
    
    def _get_salary_ytd(self, employee, year, date_to, exclude_payslip_id=None):
        """Obtener sueldo acumulado YTD desde payslips confirmados"""
        year_start = date(year, 1, 1)
        payslip_domain = [
            ('employee_id', '=', employee.id),
            ('date_to', '>=', year_start),
            ('date_to', '<=', date_to),
            ('state', 'in', ['done', 'paid']),
        ]
        if exclude_payslip_id:
            payslip_domain.append(('id', '!=', exclude_payslip_id))
        
        payslip_ids = self.env['hr.payslip'].search(payslip_domain).ids
        if not payslip_ids:
            return 0.0
        result = self.env['hr.payslip.line'].read_group(
            [('slip_id', 'in', payslip_ids), ('code', '=', 'BASIC')],
            ['total:sum'], []
        )
        return result[0]['total'] if result and result[0]['total'] else 0.0
    
    def _project_annual_salary(self, employee, salary_ytd, date_from):
        """Proyectar sueldo anual (YTD + meses restantes × salario mensual).
        Si el empleado ingresó a mitad del año, proyecta solo desde su fecha de ingreso hasta dic."""
        year = date_from.year
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        
        version = employee.current_version_id.sudo() if employee.current_version_id else False
        if not version or not version.wage:
            return salary_ytd
        
        monthly_wage = version.wage
        
        hire_date = self._get_hire_date_for_year(employee, year)
        if hire_date:
            # Empleado ingresó después del 1 de enero: proyectar solo desde ingreso hasta dic
            hire_month = hire_date.month
            if date_from.month < hire_month:
                return salary_ytd
            if date_from.month == hire_month:
                # Estamos en el mes de ingreso: proporción + meses completos restantes
                from calendar import monthrange
                days_in_hire_month = monthrange(year, hire_month)[1]
                days_worked_hire_month = days_in_hire_month - hire_date.day + 1
                first_month_proportional = monthly_wage * (days_worked_hire_month / float(days_in_hire_month))
                full_months = 12 - hire_month  # abril a dic
                projected_annual = salary_ytd + first_month_proportional + (monthly_wage * full_months)
            else:
                # Meses posteriores al ingreso: YTD + meses restantes hasta dic
                months_remaining = 13 - date_from.month
                projected_annual = salary_ytd + (monthly_wage * months_remaining)
            return projected_annual
        
        # Comportamiento original: año completo
        months_passed = date_from.month - 1
        months_remaining = 12 - months_passed
        projected_annual = salary_ytd + (monthly_wage * months_remaining)
        return projected_annual
    
    def _get_bonuses_ytd(self, employee, year, date_to, exclude_payslip_id=None):
        """Obtener bonos/horas extra/comisiones acumulados YTD"""
        year_start = date(year, 1, 1)
        payslip_domain = [
            ('employee_id', '=', employee.id),
            ('date_to', '>=', year_start),
            ('date_to', '<=', date_to),
            ('state', 'in', ['done', 'paid']),
        ]
        if exclude_payslip_id:
            payslip_domain.append(('id', '!=', exclude_payslip_id))
        
        payslip_ids = self.env['hr.payslip'].search(payslip_domain).ids
        if not payslip_ids:
            return 0.0

        result = self.env['hr.payslip.line'].read_group(
            [('slip_id', 'in', payslip_ids), ('code', 'in', self._BONUS_CODES)],
            ['total:sum'], []
        )
        return result[0]['total'] if result and result[0]['total'] else 0.0
    
    def _project_annual_bonuses(self, employee, bonuses_ytd, date_from):
        """Proyectar bonos anuales (promedio mensual × meses restantes).
        Si el empleado ingresó a mitad del año, proyecta solo desde su mes de ingreso."""
        year = date_from.year
        
        hire_date = self._get_hire_date_for_year(employee, year)
        if hire_date:
            hire_month = hire_date.month
            if date_from.month < hire_month:
                return 0.0
            months_since_hire = max(1, date_from.month - hire_month + 1)
            monthly_average = bonuses_ytd / months_since_hire
            months_remaining = 13 - date_from.month
            return bonuses_ytd + (monthly_average * months_remaining)
        
        # Comportamiento original: año completo
        months_passed = date_from.month - 1
        if months_passed <= 0:
            return bonuses_ytd * 12
        monthly_average = bonuses_ytd / months_passed
        months_remaining = 12 - months_passed
        return bonuses_ytd + (monthly_average * months_remaining)
    
    def compute_withholding_for_period(self, employee, date_from, date_to, company):
        """
        Compute ISR withholding for an employee for a given period (without payslip).
        Used for pre-calculation / review before payroll generation.
        Creates audit record and returns the same structure as compute_withholding.
        """
        self.ensure_one()
        mock_payslip = self.env['hr.payslip'].new({
            'employee_id': employee.id,
            'date_from': date_from,
            'date_to': date_to,
            'company_id': company.id,
        })
        if self.periodicity == 'biweekly' and not self._period_applies(mock_payslip):
            return {'period_amount': 0.0, 'audit_data': {'period_not_applicable': True}}
        if self.multiplicador_tope_exento_decimos:
            return self._compute_withholding_sar_2026(mock_payslip)
        return self._compute_withholding_legacy(mock_payslip)

    def _period_applies(self, payslip):
        """Check if this period applies for ISR withholding"""
        if self.periodicity != 'biweekly':
            return True
        
        if self.apply_in == 'both':
            return True
        
        # Check if first or second half
        day_from = payslip.date_from.day if payslip.date_from else 1
        is_first_half = day_from <= 15
        
        if self.apply_in == 'first_half' and is_first_half:
            return True
        if self.apply_in == 'second_half' and not is_first_half:
            return True
        
        return False
    
    def _get_ytd_payslip_ids(self, employee, year, period_end, company, exclude_payslip_id=None):
        """Get payslip ids for YTD queries. Uses hr.payslip search to avoid domain dot-notation on hr.payslip.line."""
        year_start = fields.Date.today().replace(year=year, month=1, day=1)
        payslip_domain = [
            ('employee_id', '=', employee.id),
            ('company_id', '=', company.id),
            ('date_to', '<=', period_end),
            ('date_to', '>=', year_start),
            ('state', 'in', ['done', 'paid']),
        ]
        if exclude_payslip_id:
            payslip_domain.append(('id', '!=', exclude_payslip_id))
        payslips = self.env['hr.payslip'].search(payslip_domain)
        return payslips.ids
    
    def _calculate_taxable_income_ytd(self, employee, year, period_end, company, exclude_payslip_id=None):
        """Calculate taxable income year-to-date - Optimized with read_group"""
        payslip_ids = self._get_ytd_payslip_ids(employee, year, period_end, company, exclude_payslip_id)
        if not payslip_ids:
            return 0.0
        
        line_domain = [('payslip_id', 'in', payslip_ids)]
        
        # Get basic income using read_group for better performance
        basic_lines = self.env['hr.payslip.line'].read_group(
            line_domain + [('category_id.code', '=', 'BASIC')],
            ['total:sum'],
            []
        )
        basic_total = basic_lines[0]['total'] if basic_lines else 0.0
        
        # Get variable income (isr_taxable rules)
        variable_lines = self.env['hr.payslip.line'].read_group(
            line_domain + [('salary_rule_id.isr_taxable', '=', True), ('total', '>', 0)],
            ['total:sum'],
            []
        )
        variable_total = variable_lines[0]['total'] if variable_lines else 0.0
        
        return basic_total + variable_total
    
    def _calculate_deductions_ytd(self, employee, year, period_end, company, config, exclude_payslip_id=None):
        """Calculate deductions year-to-date - Optimized with read_group"""
        payslip_ids = self._get_ytd_payslip_ids(employee, year, period_end, company, exclude_payslip_id)
        if not payslip_ids:
            return {
                'payroll': 0.0,
                'declared': 0.0,
                'medical': 0.0,
                'total': 0.0,
            }
        
        line_domain = [('payslip_id', 'in', payslip_ids)]
        
        # Get payroll deductions (from salary rules)
        deductible_rule_ids = config.deductible_rule_ids.ids
        payroll_deductions = 0.0
        if deductible_rule_ids:
            rule_lines = self.env['hr.payslip.line'].read_group(
                line_domain + [
                    ('salary_rule_id.id', 'in', deductible_rule_ids),
                    ('total', '<', 0)
                ],
                ['total:sum'],
                []
            )
            payroll_deductions = abs(rule_lines[0]['total']) if rule_lines and rule_lines[0]['total'] else 0.0
        
        # Also check isr_deductible flag (for backward compatibility),
        # excluding rules already counted via deductible_rule_ids to avoid double-counting
        deductible_extra_domain = line_domain + [
            ('salary_rule_id.isr_deductible', '=', True),
            ('total', '<', 0),
        ]
        if deductible_rule_ids:
            deductible_extra_domain.append(('salary_rule_id.id', 'not in', deductible_rule_ids))
        deductible_lines = self.env['hr.payslip.line'].read_group(
            deductible_extra_domain,
            ['total:sum'],
            []
        )
        if deductible_lines and deductible_lines[0]['total']:
            payroll_deductions += abs(deductible_lines[0]['total'])
        
        # Get input type deductions
        deductible_input_ids = config.deductible_input_type_ids.ids
        input_deductions = 0.0
        if deductible_input_ids:
            input_lines = self.env['hr.payslip.line'].read_group(
                line_domain + [
                    ('input_type_id.id', 'in', deductible_input_ids),
                    ('amount', '<', 0)
                ],
                ['amount:sum'],
                []
            )
            input_deductions = abs(input_lines[0]['amount']) if input_lines and input_lines[0]['amount'] else 0.0
        
        payroll_deductions_total = payroll_deductions + input_deductions
        
        # Get employee declared deductions (already optimized with get_ytd_amount)
        employee_deductions = self.env['l10n.hn.isr.employee_deduction'].search([
            ('employee_id', '=', employee.id),
            ('company_id', '=', company.id),
            ('year', '=', year),
            ('active', '=', True),
        ])
        
        declared_deductions = 0.0
        for deduction in employee_deductions:
            # Use the improved YTD calculation method
            # This handles annual deductions correctly (only counted once)
            # and monthly deductions correctly (counted per month)
            declared_deductions += deduction.get_ytd_amount(year, period_end)
        
        # Medical expenses (simplified - would need actual medical expense tracking)
        medical_expenses = 0.0  # TODO: Implement medical expense tracking
        
        return {
            'payroll': payroll_deductions_total,
            'declared': declared_deductions,
            'medical': medical_expenses,
            'total': payroll_deductions_total + declared_deductions + medical_expenses,
        }
    
    def _calculate_bonus_taxable(self, employee, year, salario_minimo_promedio):
        """Calculate taxable portion of 13th and 14th month bonuses"""
        exempt_limit = salario_minimo_promedio * 10  # 10x monthly minimum wage
        
        # Get 13th month payslips
        thirteenth_payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', employee.id),
            ('date_to', '>=', fields.Date.today().replace(year=year, month=1, day=1)),
            ('date_to', '<=', fields.Date.today().replace(year=year, month=12, day=31)),
            ('struct_id.code', '=', '13TH_MONTH'),
            ('state', 'in', ['done', 'paid']),
        ])
        
        thirteenth_total = sum(slip.line_ids.filtered(
            lambda l: l.salary_rule_id.code == '13TH_MONTH'
        ).mapped('total') for slip in thirteenth_payslips)
        
        thirteenth_taxable = max(0, thirteenth_total - exempt_limit)
        
        # Get 14th month payslips
        fourteenth_payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', employee.id),
            ('date_to', '>=', fields.Date.today().replace(year=year, month=1, day=1)),
            ('date_to', '<=', fields.Date.today().replace(year=year, month=12, day=31)),
            ('struct_id.code', '=', '14TH_MONTH'),
            ('state', 'in', ['done', 'paid']),
        ])
        
        fourteenth_total = sum(slip.line_ids.filtered(
            lambda l: l.salary_rule_id.code == '14TH_MONTH'
        ).mapped('total') for slip in fourteenth_payslips)
        
        fourteenth_taxable = max(0, fourteenth_total - exempt_limit)
        
        return thirteenth_taxable, fourteenth_taxable
    
    def _calculate_annual_projection(self, employee, year, period_end, taxable_ytd, deductions_ytd, config):
        """Calculate annual projection of income and deductions.
        Si el empleado ingresó a mitad del año, considera solo el período desde ingreso hasta dic."""
        year_start = fields.Date.today().replace(year=year, month=1, day=1)
        year_end = fields.Date.today().replace(year=year, month=12, day=31)
        
        if config.periodicity == 'biweekly':
            periods_per_year_full = 24
            days_per_period = 15
        else:
            periods_per_year_full = 12
            days_per_period = 30
        
        hire_date = self._get_hire_date_for_year(employee, year)
        if hire_date:
            if period_end < hire_date:
                effective_start = year_start
                periods_per_year = periods_per_year_full
                days_elapsed = (period_end - year_start).days + 1
                periods_elapsed = max(1, int(days_elapsed / days_per_period))
            else:
                effective_start = hire_date
                periods_per_year = max(1, int(((year_end - effective_start).days + 1) / days_per_period))
                days_elapsed = (period_end - effective_start).days + 1
                periods_elapsed = max(1, int(days_elapsed / days_per_period))
        else:
            effective_start = year_start
            periods_per_year = periods_per_year_full
            days_elapsed = (period_end - year_start).days + 1
            periods_elapsed = max(1, int(days_elapsed / days_per_period))
        
        periods_remaining = max(0, periods_per_year - periods_elapsed)
        
        basic_period = 0.0
        version = employee.current_version_id.sudo() if employee.current_version_id else False
        if version:
            basic_period = version.wage or 0.0
        
        projected_basic = basic_period * periods_per_year
        
        if periods_elapsed > 0:
            variable_per_period = taxable_ytd / periods_elapsed
            projected_variable = variable_per_period * periods_per_year
        else:
            projected_variable = 0.0
        
        projected_income = projected_basic + projected_variable
        
        if periods_elapsed > 0:
            deductions_per_period = deductions_ytd.get('total', 0) / periods_elapsed
            projected_deductions = deductions_per_period * periods_per_year
        else:
            projected_deductions = 0.0
        
        return {
            'projected_income': projected_income,
            'projected_deductions': projected_deductions,
            'periods_remaining': periods_remaining,
            'basic_income_ytd': basic_period * periods_elapsed,
            'variable_income_ytd': projected_variable - (basic_period * periods_per_year),
        }
    
    def _get_isr_retained_ytd(self, employee, year, period_end, current_payslip_id):
        """Get ISR retained year-to-date from previous payslips - Optimized"""
        year_start = fields.Date.today().replace(year=year, month=1, day=1)
        
        payslip_domain = [
            ('employee_id', '=', employee.id),
            ('date_to', '<', period_end),
            ('date_to', '>=', year_start),
            ('state', 'in', ['done', 'paid']),
        ]
        if current_payslip_id:
            payslip_domain.append(('id', '!=', current_payslip_id))
        payslips = self.env['hr.payslip'].search(payslip_domain)
        payslip_ids = payslips.ids
        if not payslip_ids:
            return 0.0
        
        line_domain = [
            ('payslip_id', 'in', payslip_ids),
            ('salary_rule_id.code', '=', 'ISR'),
            ('total', '<', 0),
        ]
        isr_lines = self.env['hr.payslip.line'].read_group(
            line_domain,
            ['total:sum'],
            []
        )
        
        isr_retained = abs(isr_lines[0]['total']) if isr_lines and isr_lines[0]['total'] else 0.0
        return isr_retained


class L10nHnIsrConfigBracket(models.Model):
    """ISR Configuration Tax Bracket"""
    _name = 'l10n.hn.isr.config.bracket'
    _description = 'ISR Configuration Tax Bracket'
    _order = 'sequence, from_amount'

    config_id = fields.Many2one('l10n.hn.isr.config', string='ISR Config', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10, required=True)
    from_amount = fields.Float(string='From Amount', required=True, digits=(12, 2),
                              help='Minimum taxable amount for this bracket')
    to_amount = fields.Float(string='To Amount', digits=(12, 2),
                            help='Maximum taxable amount (0 = no limit)')
    rate = fields.Float(string='Tax Rate (%)', required=True, digits=(5, 2),
                       help='Tax rate percentage for excess over base')
    fixed_quota = fields.Float(string='Fixed Quota', required=True, digits=(12, 2), default=0.0,
                              help='Fixed tax amount for this bracket (cumulative from previous brackets)')
    excess_over = fields.Float(string='Excess Over', required=True, digits=(12, 2),
                              help='Base amount for calculating excess (usually same as from_amount)')
    
    @api.constrains('from_amount', 'to_amount', 'rate', 'excess_over')
    def _check_bracket(self):
        """Validate bracket values"""
        for rec in self:
            if rec.from_amount < 0:
                raise ValidationError(_('From amount cannot be negative.'))
            if rec.to_amount > 0 and rec.to_amount <= rec.from_amount:
                raise ValidationError(_('To amount must be greater than From amount.'))
            if rec.rate < 0:
                raise ValidationError(_('Tax rate cannot be negative.'))
            if rec.excess_over < 0:
                raise ValidationError(_('Excess over cannot be negative.'))


class L10nHnIsrMedicalExpenseRule(models.Model):
    """Medical Expense Deduction Rule by Age"""
    _name = 'l10n.hn.isr.medical_expense_rule'
    _description = 'ISR Medical Expense Rule by Age'
    _order = 'age_from'

    config_id = fields.Many2one('l10n.hn.isr.config', string='ISR Config', required=True, ondelete='cascade')
    age_from = fields.Integer(string='Age From', required=True,
                              help='Minimum age for this rule')
    age_to = fields.Integer(string='Age To',
                           help='Maximum age for this rule (0 = no limit)')
    limit_amount = fields.Float(string='Limit Amount', required=True, digits=(12, 2),
                                help='Annual deduction limit for this age range')
    
    @api.constrains('age_from', 'age_to')
    def _check_age_range(self):
        """Validate age range"""
        for rec in self:
            if rec.age_from < 0:
                raise ValidationError(_('Age from cannot be negative.'))
            if rec.age_to > 0 and rec.age_to < rec.age_from:
                raise ValidationError(_('Age to must be greater than or equal to age from.'))


class L10nHnIsrEmployeeDeduction(models.Model):
    """Employee ISR Deductions - Declared deductions that reduce taxable income"""
    _name = 'l10n.hn.isr.employee_deduction'
    _description = 'Employee ISR Deduction'
    _order = 'year desc, employee_id, date_start'

    name = fields.Char(string='Description', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True, ondelete='cascade')
    version_id = fields.Many2one('hr.version', string='Contract Version', 
                                  help='Contract version associated with this deduction',
                                  ondelete='set null', index=True,
                                  domain="[('employee_id', '=', employee_id)]")
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                default=lambda self: self.env.company)
    year = fields.Integer(string='Year', required=True, index=True,
                        default=lambda self: fields.Date.today().year)
    
    deduction_type_id = fields.Many2one(
        'l10n.hn.isr.deduction.type',
        string='Tipo de Deducción',
        required=True,
        ondelete='restrict',
        default=lambda self: self.env['l10n.hn.isr.deduction.type'].search(
            [('code', '=', 'otros')], limit=1
        ),
        help='Tipo de deducción. Configure los tipos en Nómina Honduras > ISR > Tipos de Deducción.')
    
    amount = fields.Float(string='Amount', required=True, digits=(12, 2),
                         help='Monto de la deducción. Para aportaciones anuales únicas, ingrese el monto total anual. Para mensuales, ingrese el monto mensual.')
    periodicity = fields.Selection([
        ('monthly', 'Mensual (Aportaciones Regulares)'),
        ('annual', 'Anual (Aportación Única)'),
        ('per_payslip', 'Por Recibo de Nómina'),
    ], string='Periodicity', required=True, default='monthly',
       help='Periodicidad de la deducción. Mensual: aportaciones regulares comprometidas. Anual: aportación única al año.')

    apply_in_quincena = fields.Selection([
        ('both', 'Ambas quincenas'),
        ('first', 'Solo 1ra quincena'),
        ('second', 'Solo 2da quincena'),
    ], string='Aplicar en quincena(s)', default='both',
       help='Para nómina quincenal: en qué quincena(s) se descuenta. '
            'Ambas: se prorratea (ej. 50 en cada una para 100 mensual). '
            'Solo 1ra/2da: se deduce el monto completo en esa quincena.')
    
    is_self_paid = fields.Boolean(string='Pagado por Cuenta Propia', default=True,
                                  help='Indica si esta deducción es pagada directamente por el empleado (no se descuenta de nómina). '
                                       'Estas deducciones son reportadas por el empleado a RRHH para efectos de cálculo de ISR.')
    
    date_start = fields.Date(string='Start Date', required=True,
                            default=lambda self: fields.Date.today())
    date_end = fields.Date(string='End Date',
                          help='End date (empty = no end date)')
    
    active = fields.Boolean(string='Active', default=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create employee deduction and auto-link to version if possible.
        Si se crea desde contrato (version_id), completar employee_id desde la versión."""
        for vals in vals_list:
            if vals.get('version_id') and not vals.get('employee_id'):
                version = self.env['hr.version'].browse(vals['version_id'])
                if version.exists() and version.employee_id:
                    vals['employee_id'] = version.employee_id.id
        deductions = super().create(vals_list)
        
        # Auto-link to version if employee has a version that overlaps
        for deduction in deductions:
            if deduction.employee_id:
                # Find version that overlaps with deduction period
                deduction_start = deduction.date_start or date.min
                deduction_end = deduction.date_end or date.max
                
                version = self.env['hr.version'].search([
                    ('employee_id', '=', deduction.employee_id.id),
                    ('contract_date_start', '<=', deduction_end),
                    '|',
                    ('contract_date_end', '=', False),
                    ('contract_date_end', '>=', deduction_start)
                ], order='contract_date_start desc', limit=1)
                
                if version:
                    deduction.write({'version_id': version.id})
        
        return deductions
    
    @api.onchange('deduction_type_id')
    def _onchange_deduction_type_id(self):
        """Set is_self_paid based on deduction type"""
        if self.deduction_type_id:
            self.is_self_paid = self.deduction_type_id.is_self_paid
    
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        """Validate date range"""
        for rec in self:
            if rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_('End date must be after start date.'))
    
    @api.constrains('periodicity', 'amount')
    def _check_annual_deduction(self):
        """Validate annual deduction logic"""
        for rec in self:
            if rec.periodicity == 'annual' and rec.amount <= 0:
                raise ValidationError(_('Annual deduction amount must be greater than zero.'))
            if rec.periodicity == 'monthly' and rec.amount <= 0:
                raise ValidationError(_('Monthly deduction amount must be greater than zero.'))
    
    def get_amount_for_period(self, period_start, period_end):
        """Get deduction amount for a specific period
        
        For annual deductions: returns the full amount only once per year (when period includes the year)
        For monthly deductions: returns the monthly amount for each period
        For per_payslip: returns the amount for the specific payslip period
        """
        self.ensure_one()
        if not self.active:
            return 0.0
        
        # Check if deduction is active for this period
        if self.date_start > period_end:
            return 0.0
        if self.date_end and self.date_end < period_start:
            return 0.0
        
        # Check if period overlaps with deduction date range
        period_start_effective = max(period_start, self.date_start)
        period_end_effective = min(period_end, self.date_end) if self.date_end else period_end
        
        if period_start_effective > period_end_effective:
            return 0.0
        
        if self.periodicity == 'annual':
            # Annual: return full amount only if this period is within the deduction year
            # and the deduction date range overlaps with this period
            if period_start.year == self.year and period_start_effective <= period_end_effective:
                # For annual deductions, we need to ensure it's only counted once
                # Check if this period is the first period that includes the deduction date
                if period_start <= self.date_start <= period_end:
                    return self.amount
            return 0.0
        elif self.periodicity == 'monthly':
            # Monthly: return monthly amount for each period that overlaps
            # Only count if the period overlaps with the deduction date range
            if period_start_effective <= period_end_effective:
                return self.amount
            return 0.0
        elif self.periodicity == 'per_payslip':
            # Per payslip: return amount for this specific payslip period
            if period_start_effective <= period_end_effective:
                return self.amount
            return 0.0
        
        return 0.0
    
    def get_ytd_amount(self, year, period_end):
        """Get total deduction amount year-to-date up to period_end
        
        This method correctly handles:
        - Annual deductions: counted only once when period_end >= date_start
        - Monthly deductions: counted for each month from start_date to period_end
        - Per payslip: would need actual payslip tracking (not implemented yet)
        """
        self.ensure_one()
        if not self.active or self.year != year:
            return 0.0
        
        # Check if deduction is active for the period
        if self.date_start > period_end:
            return 0.0
        if self.date_end and self.date_end < period_end:
            # If deduction has ended, use end date
            effective_end = self.date_end
        else:
            effective_end = period_end
        
        if self.periodicity == 'annual':
            # Annual: return full amount only once if period_end is after or equal to date_start
            # This ensures annual contributions are counted only once per year
            if period_end >= self.date_start:
                return self.amount
            return 0.0
        elif self.periodicity == 'monthly':
            # Monthly: calculate number of months from deduction start to period_end
            # Start counting from deduction start date or year start, whichever is later
            year_start = fields.Date.today().replace(year=year, month=1, day=1)
            start_date = max(year_start, self.date_start)
            end_date = min(effective_end, period_end)
            
            if start_date > end_date:
                return 0.0
            
            # Count number of months (including partial months)
            # We count each month where the deduction is active
            months = 0
            current_month = start_date.replace(day=1)
            end_month = end_date.replace(day=1)
            
            while current_month <= end_month:
                # Check if this month overlaps with the deduction period
                month_start = max(current_month, start_date)
                month_end = min(
                    current_month + relativedelta(months=1) - relativedelta(days=1),
                    end_date
                )
                if month_start <= month_end:
                    months += 1
                current_month += relativedelta(months=1)
            
            return self.amount * months
        elif self.periodicity == 'per_payslip':
            # Per payslip: would need to track actual payslips
            # For now, we could approximate by counting periods
            # But ideally this should be linked to actual payslip records
            return 0.0
        
        return 0.0

    def _is_biweekly_payslip(self, payslip):
        """True if payslip structure is biweekly."""
        if not payslip or not payslip.struct_id:
            return False
        struct = payslip.struct_id
        if hasattr(struct, 'periodicity') and struct.periodicity in ('biweekly', 'bi-weekly'):
            return True
        if struct.type_id:
            sched = struct.type_id.default_schedule_pay or 'monthly'
            return sched in ('bi-weekly', 'biweekly')
        return False

    def _is_first_quincena(self, payslip):
        """True if payslip period is first half of month (days 1-15)."""
        if not payslip or not payslip.date_to:
            return False
        return payslip.date_to.day <= 15

    def get_amount_for_payslip(self, payslip):
        """Get deduction amount for this payslip period, with proration for biweekly.
        Used by salary rules to show deductions that are descontadas de nómina (is_self_paid=False).
        Respeta apply_in_quincena: si es 'first' o 'second', solo aplica en esa quincena."""
        self.ensure_one()
        if not payslip or not payslip.date_from or not payslip.date_to:
            return 0.0
        base = self.get_amount_for_period(payslip.date_from, payslip.date_to)
        if base == 0:
            return 0.0
        # Para nómina quincenal: verificar apply_in_quincena
        if self._is_biweekly_payslip(payslip):
            is_first = self._is_first_quincena(payslip)
            if self.apply_in_quincena == 'first' and not is_first:
                return 0.0
            if self.apply_in_quincena == 'second' and is_first:
                return 0.0
            # both: prorratear mensual para cada quincena
            if self.periodicity == 'monthly' and self.apply_in_quincena == 'both':
                period_days = (payslip.date_to - payslip.date_from).days + 1
                std_days = payslip.standard_period_days or 30
                if std_days < 25 and period_days < 25:
                    base = base * (period_days / 30.0)
            # first/second: monto completo en esa quincena (no prorratear)
        else:
            # Nómina mensual: prorratear solo si período corto
            if self.periodicity == 'monthly':
                period_days = (payslip.date_to - payslip.date_from).days + 1
                std_days = payslip.standard_period_days or 30
                if std_days < 25 and period_days < 25:
                    base = base * (period_days / 30.0)
        return base

    @api.model
    def get_total_payroll_deductions_for_payslip(self, payslip):
        """Sum of all employee deductions descontadas de nómina (is_self_paid=False)
        for the payslip period. Returns positive amount (caller negates for DED)."""
        if not payslip or not payslip.employee_id or not payslip.date_from:
            return 0.0
        deductions = self.search([
            ('employee_id', '=', payslip.employee_id.id),
            ('year', '=', payslip.date_from.year),
            ('active', '=', True),
            ('is_self_paid', '=', False),
            ('company_id', '=', payslip.company_id.id),
        ])
        return sum(d.get_amount_for_payslip(payslip) for d in deductions)

    @api.model
    def get_annual_deductions_breakdown(self, employee, year, company_id=None):
        """Desglose anual por categoría para Establecer ISR.
        Retorna dict: membership (colegiación), pension (AFP), other (otros)."""
        if not employee or not year:
            return {'membership': 0.0, 'pension': 0.0, 'other': 0.0}
        domain = [
            ('employee_id', '=', employee.id),
            ('year', '=', year),
            ('active', '=', True),
        ]
        if company_id:
            domain.append(('company_id', '=', company_id))
        deductions = self.search(domain)
        membership = pension = other = 0.0
        for d in deductions:
            if d.periodicity == 'annual':
                amt = d.amount
            elif d.periodicity == 'monthly':
                amt = d.amount * 12
            elif d.periodicity == 'per_payslip':
                amt = d.amount * 12
            else:
                amt = 0.0
            code = (d.deduction_type_id.code or '') if d.deduction_type_id else ''
            if code == 'colegio_profesional':
                membership += amt
            elif code in ('afp', 'afp_nomina'):
                pension += amt
            elif code == 'otros':
                other += amt
        return {'membership': membership, 'pension': pension, 'other': other}

    @api.model
    def get_amount_by_type_for_payslip(self, payslip, deduction_type_code):
        """Sum of employee deductions for a specific type (by code) descontadas de nómina.
        Returns positive amount (caller negates for DED)."""
        if not payslip or not payslip.employee_id or not payslip.date_from:
            return 0.0
        deductions = self.search([
            ('employee_id', '=', payslip.employee_id.id),
            ('year', '=', payslip.date_from.year),
            ('active', '=', True),
            ('is_self_paid', '=', False),
            ('company_id', '=', payslip.company_id.id),
            ('deduction_type_id.code', '=', deduction_type_code),
        ])
        return sum(d.get_amount_for_payslip(payslip) for d in deductions)

    @api.model
    def diagnose_afp_for_payslip(self, payslip):
        """Diagnóstico: por qué la deducción AFP puede aparecer en 0.
        Retorna un dict con la información para depuración."""
        res = {
            'payslip_id': payslip.id if payslip else None,
            'employee': payslip.employee_id.name if payslip and payslip.employee_id else None,
            'date_from': str(payslip.date_from) if payslip and payslip.date_from else None,
            'date_to': str(payslip.date_to) if payslip and payslip.date_to else None,
            'company': payslip.company_id.name if payslip and payslip.company_id else None,
            'struct': payslip.struct_id.name if payslip and payslip.struct_id else None,
            'isr_excluded': payslip.employee_id.isr_excluded if payslip and payslip.employee_id else None,
            'deductions_found': 0,
            'deductions_detail': [],
            'total': 0.0,
            'reason': None,
        }
        if not payslip or not payslip.employee_id or not payslip.date_from:
            res['reason'] = 'Payslip sin employee_id o date_from'
            return res
        deductions = self.search([
            ('employee_id', '=', payslip.employee_id.id),
            ('year', '=', payslip.date_from.year),
            ('active', '=', True),
            ('is_self_paid', '=', False),
            ('company_id', '=', payslip.company_id.id),
            ('deduction_type_id.code', '=', 'afp_nomina'),
        ])
        res['deductions_found'] = len(deductions)
        if not deductions:
            res['reason'] = (
                'No hay deducciones tipo AFP Descontado de Nómina con is_self_paid=False '
                'para este empleado, año y empresa.'
            )
            return res
        is_biweekly = False
        if payslip.struct_id:
            p = getattr(payslip.struct_id, 'periodicity', None)
            if p in ('biweekly', 'bi-weekly'):
                is_biweekly = True
            elif payslip.struct_id.type_id:
                sched = payslip.struct_id.type_id.default_schedule_pay or 'monthly'
                is_biweekly = sched in ('bi-weekly', 'biweekly')
        is_first_quincena = payslip.date_to and payslip.date_to.day <= 15
        for d in deductions:
            base = d.get_amount_for_period(payslip.date_from, payslip.date_to)
            amt = d.get_amount_for_payslip(payslip)
            detail = {
                'id': d.id,
                'amount': d.amount,
                'periodicity': d.periodicity,
                'date_start': str(d.date_start),
                'date_end': str(d.date_end) if d.date_end else None,
                'apply_in_quincena': d.apply_in_quincena or 'both',
                'get_amount_for_period': base,
                'get_amount_for_payslip': amt,
            }
            if base == 0:
                detail['why_period_0'] = (
                    'date_start > period_end' if d.date_start > payslip.date_to else
                    'date_end < period_start' if d.date_end and d.date_end < payslip.date_from else
                    'sin solapamiento'
                )
            elif amt == 0 and is_biweekly:
                if d.apply_in_quincena == 'second' and is_first_quincena:
                    detail['why_payslip_0'] = "apply_in_quincena='second' pero payslip es 1ra quincena"
                elif d.apply_in_quincena == 'first' and not is_first_quincena:
                    detail['why_payslip_0'] = "apply_in_quincena='first' pero payslip es 2da quincena"
            res['deductions_detail'].append(detail)
        res['total'] = sum(d.get_amount_for_payslip(payslip) for d in deductions)
        res['is_biweekly'] = is_biweekly
        res['is_first_quincena'] = is_first_quincena
        return res


class L10nHnIsrAudit(models.Model):
    """ISR Calculation Audit - Detailed calculation traceability"""
    _name = 'l10n.hn.isr.audit'
    _description = 'ISR Calculation Audit'
    _order = 'year desc, period_start desc, employee_id'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company', required=True, index=True)
    year = fields.Integer(string='Year', required=True, index=True)
    period_start = fields.Date(string='Period Start', required=True, index=True)
    period_end = fields.Date(string='Period End', required=True, index=True)
    
    payslip_id = fields.Many2one('hr.payslip', string='Payslip', ondelete='set null', index=True)
    config_id = fields.Many2one('l10n.hn.isr.config', string='ISR Config Used', readonly=True, index=True)
    
    # Income breakdown
    salary_annual = fields.Float(string='Salary Annual (R)', digits=(12, 2),
                                 help='Proyectado sueldo anual (SAR 2026)')
    basic_income_ytd = fields.Float(string='Basic Income YTD', digits=(12, 2))
    variable_income_ytd = fields.Float(string='Variable Income YTD', digits=(12, 2),
                                       help='Bonuses, commissions, etc.')
    thirteenth_month_taxable = fields.Float(string='13th Month Taxable', digits=(12, 2))
    fourteenth_month_taxable = fields.Float(string='14th Month Taxable', digits=(12, 2))
    excess_vacations = fields.Float(string='Excess Vacations Taxable', digits=(12, 2),
                                    help='Exceso vacaciones gravable (SAR 2026)')
    total_taxable_income_ytd = fields.Float(string='Total Taxable Income YTD', digits=(12, 2))
    
    # Deductions breakdown
    payroll_deductions_ytd = fields.Float(string='Payroll Deductions YTD', digits=(12, 2),
                                          help='Deductions from salary rules (AFP, etc.)')
    employee_declared_deductions_ytd = fields.Float(string='Employee Declared Deductions YTD', digits=(12, 2),
                                                    help='Deductions declared by employee')
    medical_expenses_ytd = fields.Float(string='Medical Expenses YTD', digits=(12, 2))
    total_deductions_ytd = fields.Float(string='Total Deductions YTD', digits=(12, 2))
    
    # Projection
    projected_annual_income = fields.Float(string='Projected Annual Income', digits=(12, 2))
    projected_annual_deductions = fields.Float(string='Projected Annual Deductions', digits=(12, 2))
    projected_taxable_base = fields.Float(string='Projected Taxable Base', digits=(12, 2))
    
    # ISR calculation
    isr_annual_calculated = fields.Float(string='ISR Annual Calculated', digits=(12, 2))
    isr_retained_ytd = fields.Float(string='ISR Retained YTD', digits=(12, 2))
    isr_balance = fields.Float(string='ISR Balance', digits=(12, 2),
                              help='Remaining ISR to withhold')
    isr_period_amount = fields.Float(string='ISR Period Amount', digits=(12, 2),
                                    help='ISR withheld in this period')
    
    # Additional info
    periods_remaining = fields.Integer(string='Periods Remaining', 
                                      help='Number of periods remaining in the year')
    calculation_notes = fields.Text(string='Calculation Notes',
                                   help='Additional notes about the calculation')
    
    # Computed fields for reporting
    period_month = fields.Char(string='Month', compute='_compute_period_info', store=True, index=True)
    period_year_month = fields.Char(string='Year-Month', compute='_compute_period_info', store=True, index=True)
    
    @api.depends('period_start', 'year')
    def _compute_period_info(self):
        """Compute period month and year-month for grouping"""
        month_names = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        for rec in self:
            if rec.period_start:
                rec.period_month = month_names.get(rec.period_start.month, '')
                rec.period_year_month = rec.period_start.strftime('%Y-%m')
            else:
                rec.period_month = ''
                rec.period_year_month = ''
    
    def action_open_report_wizard(self):
        """Open ISR audit report wizard"""
        self.ensure_one()
        return {
            'name': _('Reportes de Auditoría ISR'),
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.hn.isr.audit.report',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_year': self.year,
                'default_company_id': self.company_id.id,
                'default_employee_ids': [(6, 0, [self.employee_id.id])],
            },
        }
