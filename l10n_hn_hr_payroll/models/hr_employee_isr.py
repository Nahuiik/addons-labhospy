# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik - Establecer ISR por empleado (flujo legacy)

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class HrIsrEmployee(models.Model):
    _name = "hr.isr.employee"
    _description = "ISR Employee"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'name ASC'

    department_id = fields.Many2one("hr.department", "Departamento")
    employee_ids = fields.One2many("hr.isr.employee.detail", "parent_id", "Detalle")
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('validated', 'Validado'),
    ], "Estado", default='draft')
    isr_id = fields.Many2one("hr.isr", "ISR", required=True)
    name = fields.Char("Año", required=True)
    exempt_salary = fields.Float("Salario Exento", compute="_compute_exempt_salary", store=True)

    @api.depends('isr_id', 'isr_id.exempt_salary', 'start_date', 'end_date')
    def _compute_exempt_salary(self):
        """Salario exento: Configuración ISR > hr.isr (legacy)"""
        for rec in self:
            exempt = rec.isr_id.exempt_salary if rec.isr_id else 0
            if not exempt and (rec.start_date or rec.end_date):
                year = (rec.end_date or rec.start_date).year
                config = self.env['l10n.hn.isr.config'].search([
                    ('year', '=', year),
                    ('company_id', '=', self.env.company.id),
                    ('state', '=', 'validated'),
                    ('active', '=', True)
                ], limit=1)
                if config and config.salario_exento:
                    exempt = config.salario_exento
                elif config:
                    exempt = config._get_exempt_monthly_threshold()
            rec.exempt_salary = exempt or 0
    pay_periodicity = fields.Selection([
        ('bi-weekly', 'Quincenal'),
        ('monthly', 'Mensual'),
    ], "Periodicidad Pago", default='bi-weekly')
    start_date = fields.Date("Fecha Inicio")
    end_date = fields.Date("Fecha Final")
    pay_number = fields.Integer("# Pagos")
    remaining_payments = fields.Integer("# Pagos Restantes")
    include_in = fields.Selection([
        ('first', 'Primera quincena'),
        ('second', 'Segunda quincena'),
        ('both', 'Ambos pagos'),
    ], string="Incluir en", default="first")

    @api.onchange('pay_number')
    def init_remaining_payments(self):
        self.remaining_payments = self.pay_number

    def set_isr_contract(self):
        for detail in self.employee_ids:
            version = detail.version_id
            if not version:
                version = detail.employee_id.current_version_id.sudo() if detail.employee_id.current_version_id else False
                detail.version_id = version

            if version and detail.total_tax > 0:
                version.amount_isr_calculated = detail.isr_fee
                version.colegiacion_anual = detail.amount_membership
                version.pension_privada_anual = detail.amount_pension
                version.otras_deducciones_anual = detail.other_expenses
            elif detail:
                detail.is_ok = False
        self.write({'state': 'validated'})

    def return_to_draft(self):
        self.write({'state': 'draft'})

    def calculate_isr(self):
        if not self.employee_ids:
            return
        if self.pay_number <= 0:
            raise ValidationError(_('El número de pagos debe de ser mayor que cero'))
        for employee in self.employee_ids:
            retention_total = 0
            for line in self.isr_id.isr_range_ids:
                if line.rate > 0:
                    if employee.total_base > line.amount_from:
                        if employee.total_base < line.amount_to:
                            retention_total += (employee.total_base - line.amount_from) * (line.rate / 100)
                        elif line.amount_to > 0:
                            retention_total += (line.amount_to - line.amount_from) * (line.rate / 100)
                        else:
                            retention_total += (employee.total_base - line.amount_from) * (line.rate / 100)
            employee.total_tax = retention_total
            employee.isr_fee = retention_total / self.pay_number
            employee.is_ok = employee.total_tax > 0

    def calculate_isr_one_line(self, line):
        retention_total = 0
        for l in self.isr_id.isr_range_ids:
            if l.rate > 0 and line.total_base > l.amount_from:
                if line.total_base < l.amount_to:
                    retention_total += (line.total_base - l.amount_from) * (l.rate / 100)
                elif l.amount_to > 0:
                    retention_total += (l.amount_to - l.amount_from) * (l.rate / 100)
                else:
                    retention_total += (line.total_base - l.amount_from) * (l.rate / 100)
        line.total_tax = retention_total
        line.isr_fee = retention_total / self.pay_number if self.pay_number else 0
        line.is_ok = line.total_tax > 0

    def get_employees(self):
        self.employee_ids.unlink()
        if not self.start_date or not self.end_date:
            raise UserError(_('Debe definir Fecha Inicio y Fecha Final.'))
        rest = self.end_date.month - self.start_date.month + 1
        # Incluir empleados con salario mayor al exento, o con otros ingresos/HE que
        # pueden hacerlos gravables (salario base exento pero total con HE/OI puede exceder)
        exempt = self.exempt_salary or 0
        domain = [
            ('active', '=', True),
            ('current_version_id', '!=', False),
            ('isr_excluded', '=', False),
            '|',
            ('current_version_id.wage', '>', exempt),
            ('current_version_id.amount_other_income', '>', 0),
        ]
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        employees = self.env["hr.employee"].search(domain)
        Detail = self.env["hr.isr.employee.detail"]
        medical_default = self.isr_id.medical_expense or 40000.0

        from calendar import monthrange

        for emp in employees:
            v = emp.current_version_id.sudo() if emp.current_version_id else False
            other_entries = (v.otros_ingresos_anual or 0)
            # RAP annual for ISR deduction:
            # Priority: version.rap_fee (set by Establecer RAP) → fallback to formula
            rap_annual = 0.0
            if not emp.rap_excluded:
                if v.rap_fee:
                    rap_config = v.rap_setup_id
                    if rap_config:
                        if rap_config.pay_periodicity == 'weekly':
                            rap_annual = round(v.rap_fee * 52, 2)
                        elif rap_config.pay_periodicity == 'bi-weekly':
                            rap_annual = round(v.rap_fee * 24, 2)
                        else:
                            rap_annual = round(v.rap_fee * 12, 2)
                    else:
                        rap_annual = round(v.rap_fee * 24, 2)
                else:
                    ihss_settings = self.env['l10n.hn.ihss.settings'].search(
                        [('state', '=', 'validated')], limit=1)
                    rap_settings = self.env['l10n.hn.rap.settings'].search(
                        [('state', '=', 'validated')], limit=1)
                    if ihss_settings and rap_settings:
                        wage = v.wage or 0.0
                        ivm_ceiling = ihss_settings.ivm_ceiling_monthly
                        rap_rate = rap_settings.foviif_employee_rate / 100.0
                        if wage > ivm_ceiling:
                            rap_monthly = round((wage - ivm_ceiling) * rap_rate, 2)
                            rap_annual = rap_monthly * 12
            # Calcular total_incomes proporcional a fecha de ingreso
            hire_start = v.contract_date_start
            period_start = self.start_date
            if hire_start and hire_start > period_start:
                # Mes de ingreso proporcional + meses completos restantes
                hire_month = hire_start.month
                year_for_cal = hire_start.year
                days_in_month = monthrange(year_for_cal, hire_month)[1]
                days_worked = days_in_month - hire_start.day + 1
                first_month_income = (v.wage or 0) * (days_worked / float(days_in_month))
                full_months = self.end_date.month - hire_month
                total_incomes = first_month_income + (v.wage or 0) * full_months + other_entries
            else:
                total_incomes = (v.wage or 0) * rest + other_entries
            # Deducciones: modelo l10n.hn.isr.employee_deduction + versión (se suman ambas)
            year = self.start_date.year
            company_id = emp.company_id.id if emp.company_id else self.env.company.id
            breakdown = self.env['l10n.hn.isr.employee_deduction'].get_annual_deductions_breakdown(
                emp, year, company_id
            )
            amount_membership = breakdown['membership'] + (v.colegiacion_anual or 0)
            amount_pension = breakdown['pension'] + (v.pension_privada_anual or 0)
            other_expenses = breakdown['other'] + (v.otras_deducciones_anual or 0)
            vals = {
                'wage': v.wage,
                'employee_id': emp.id,
                'version_id': v.id,
                'parent_id': self.id,
                'medical_expense': medical_default,
                'total_incomes': total_incomes,
                'amount_rap': rap_annual,
                'amount_ivm': self.isr_id.amount_ivm,
                'amount_membership': amount_membership,
                'amount_pension': amount_pension,
                'other_expenses': other_expenses,
                'other_entries': other_entries,
            }
            Detail.create(vals)


class HrIsrEmployeeDetail(models.Model):
    _name = "hr.isr.employee.detail"
    _description = "ISR Employee Detail"
    _rec_name = "employee_id"
    _order = "employee_id"

    parent_id = fields.Many2one("hr.isr.employee", "ISR Año", ondelete='cascade')
    employee_id = fields.Many2one("hr.employee", "Empleado", required=True)
    version_id = fields.Many2one("hr.version", "Versión contrato")
    hire_date = fields.Date(
        string="Fecha de Ingreso",
        related="version_id.contract_date_start",
        readonly=True,
        help="Fecha de ingreso del contrato (para proyección ISR proporcional).",
    )
    total_incomes = fields.Float("Total Ingresos")
    amount_membership = fields.Float("Colegiaturas")
    amount_pension = fields.Float("Pensión Previsión Privada",
                                  help="Aportaciones a fondos de pensiones privados para deducción ISR")
    medical_expense = fields.Float("Gastos Médicos")
    amount_rap = fields.Float("RAP")
    amount_ivm = fields.Float("Invalidez Vejez y Muerte")
    other_expenses = fields.Float("Otros Gastos")
    total_base = fields.Float("Total Base Impositiva", compute='_compute_total_base', store=True)
    total_tax = fields.Float("Total Impuesto")
    isr_fee = fields.Float("Deducción")
    is_ok = fields.Boolean("A procesar/Procesado")
    wage = fields.Float(string="Salario")
    exempt_value = fields.Float(compute="_compute_exempt_value", string="Valor Exento")
    net_salary = fields.Float(compute='_compute_net_salary', string="Salario Neto")
    other_entries = fields.Float(string='Otros Ingresos')

    @api.depends("total_incomes", "amount_membership", "amount_pension", "medical_expense", "amount_rap", "amount_ivm", "other_expenses")
    def _compute_total_base(self):
        for rec in self:
            rec.total_base = (
                rec.total_incomes - rec.amount_membership - rec.amount_pension - rec.medical_expense
                - rec.amount_rap - rec.amount_ivm - rec.other_expenses
            )

    @api.onchange('wage', 'other_entries', 'amount_membership', 'amount_pension', 'other_expenses')
    def _onchange_recompute(self):
        self._recompute_all()

    def _recompute_all(self):
        if not self.parent_id:
            return
        from calendar import monthrange
        hire_start = self.version_id.contract_date_start if self.version_id else None
        period_start = self.parent_id.start_date
        period_end = self.parent_id.end_date
        if hire_start and period_start and hire_start > period_start:
            hire_month = hire_start.month
            days_in_month = monthrange(hire_start.year, hire_month)[1]
            days_worked = days_in_month - hire_start.day + 1
            first_month_income = (self.wage or 0) * (days_worked / float(days_in_month))
            full_months = (period_end.month if period_end else 12) - hire_month
            self.total_incomes = first_month_income + (self.wage or 0) * full_months + (self.other_entries or 0)
        else:
            months = (period_end.month - period_start.month + 1) if (period_start and period_end) else 12
            self.total_incomes = (self.wage or 0) * months + (self.other_entries or 0)
        self.parent_id.calculate_isr_one_line(self)
        if self.version_id and self.isr_fee:
            self.version_id.amount_isr_calculated = self.isr_fee

    @api.depends('parent_id', 'parent_id.exempt_salary', 'medical_expense')
    def _compute_exempt_value(self):
        for rec in self:
            try:
                rec.exempt_value = max(0, (rec.parent_id.exempt_salary or 0) * 12 - (rec.medical_expense or 0))
            except Exception:
                rec.exempt_value = 0

    @api.depends('total_incomes', 'medical_expense', 'exempt_value', 'amount_rap', 'amount_membership', 'amount_pension', 'other_expenses')
    def _compute_net_salary(self):
        for rec in self:
            rec.net_salary = (
                (rec.total_incomes or 0) - (rec.medical_expense or 0) - (rec.amount_rap or 0)
                - (rec.amount_membership or 0) - (rec.amount_pension or 0) - (rec.other_expenses or 0)
                - (rec.exempt_value or 0)
            )
