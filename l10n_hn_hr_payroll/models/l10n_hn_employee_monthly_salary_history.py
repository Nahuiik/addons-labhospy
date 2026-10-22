# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from calendar import monthrange
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class L10nHnEmployeeMonthlySalaryHistory(models.Model):
    _name = 'l10n.hn.employee.monthly.salary.history'
    _description = 'Historial salarial mensual (HN)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'year desc, month desc, employee_id'

    name = fields.Char(string='Referencia', compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, default=lambda self: self.env.company,
        index=True, tracking=True,
    )
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', required=True, ondelete='cascade', index=True,
        tracking=True,
    )
    year = fields.Integer(string='Año', required=True, tracking=True)
    month = fields.Integer(string='Mes', required=True, tracking=True)

    currency_id = fields.Many2one(
        related='company_id.currency_id', store=True, readonly=True,
    )

    # Desglose
    periodicity_snapshot = fields.Selection(
        [
            ('weekly', 'Semanal'),
            ('biweekly', 'Quincenal'),
            ('monthly', 'Mensual'),
        ],
        string='Periodicidad (instantánea)',
        help='Periodicidad del contrato vigente al consolidar el registro.',
        tracking=True,
    )
    amount_net = fields.Monetary(
        string='Neto nómina',
        currency_field='currency_id',
        help='Suma del neto de recibos del mes (quincenas sumadas o período mensual).',
        tracking=True,
    )
    amount_commission = fields.Monetary(
        string='Comisiones (reglas)',
        currency_field='currency_id',
        help='Suma de líneas de nómina marcadas como comisión en la regla salarial.',
        tracking=True,
    )
    amount_monthly_display = fields.Monetary(
        string='Salario mensual (mostrado)',
        currency_field='currency_id',
        compute='_compute_amount_monthly_display', store=True,
        help='Neto nómina, más comisiones si el empleado está marcado para sumarlas '
             '(evitar doble conteo si el neto ya incluye comisiones).',
    )

    data_source = fields.Selection(
        [
            ('payslip', 'Desde nómina'),
            ('import', 'Importación Excel'),
            ('manual', 'Manual'),
        ],
        string='Origen', default='payslip', required=True, tracking=True,
    )

    payslip_ids = fields.Many2many(
        'hr.payslip',
        'l10n_hn_emp_monthly_salary_hist_payslip_rel',
        'history_id', 'payslip_id',
        string='Recibos agregados',
        readonly=True,
    )
    payslip_count = fields.Integer(compute='_compute_payslip_count')

    # Datos empleado para listado (instantánea al crear / regenerar)
    identification_snapshot = fields.Char(string='DNI (instantánea)', readonly=True)
    hire_date_snapshot = fields.Date(string='Fecha ingreso (instantánea)', readonly=True)
    department_id = fields.Many2one('hr.department', string='Departamento', readonly=True)
    job_id = fields.Many2one('hr.job', string='Puesto', readonly=True)

    # Integración aumentos
    historical_increase_ids = fields.Many2many(
        'hr.historical.salary.increase',
        compute='_compute_historical_increase_ids',
        compute_sudo=False,
        string='Aumentos registrados en el mes',
    )
    historical_increase_count = fields.Integer(
        compute='_compute_historical_increase_count',
        compute_sudo=False,
    )
    previous_month_display = fields.Monetary(
        string='Mes anterior (mostrado)',
        currency_field='currency_id',
        compute='_compute_month_comparison',
    )
    delta_vs_previous = fields.Monetary(
        string='Variación vs mes ant.',
        currency_field='currency_id',
        compute='_compute_month_comparison',
    )

    notes = fields.Text(string='Notas')

    _l10n_hn_monthly_salary_employee_period_uniq = models.Constraint(
        'unique(employee_id, year, month)',
        'Ya existe un historial mensual para este empleado y período.',
    )

    @api.constrains('year', 'month')
    def _check_year_month(self):
        for rec in self:
            if rec.year < 2000 or rec.year > 2100:
                raise ValidationError(_('Año fuera de rango válido.'))
            if rec.month < 1 or rec.month > 12:
                raise ValidationError(_('Mes debe estar entre 1 y 12.'))

    @api.depends('employee_id', 'year', 'month')
    def _compute_name(self):
        for rec in self:
            if rec.employee_id and rec.year and rec.month:
                rec.name = '%s / %04d-%02d' % (
                    rec.employee_id.name or '',
                    rec.year,
                    rec.month,
                )
            else:
                rec.name = _('Nuevo')

    @api.depends('payslip_ids')
    def _compute_payslip_count(self):
        for rec in self:
            rec.payslip_count = len(rec.payslip_ids)

    @api.depends(
        'amount_net',
        'amount_commission',
        'employee_id',
        'employee_id.l10n_hn_add_commission_to_monthly_display',
        'employee_id.l10n_hn_receives_commission',
    )
    def _compute_amount_monthly_display(self):
        for rec in self:
            emp = rec.employee_id
            add_comm = emp.l10n_hn_add_commission_to_monthly_display if emp else False
            receives = emp.l10n_hn_receives_commission if emp else False
            if add_comm or (receives and rec.amount_commission):
                rec.amount_monthly_display = (rec.amount_net or 0.0) + (rec.amount_commission or 0.0)
            else:
                rec.amount_monthly_display = rec.amount_net

    @api.depends('employee_id', 'year', 'month')
    def _compute_historical_increase_ids(self):
        Inc = self.env['hr.historical.salary.increase']
        for rec in self:
            if not rec.employee_id or not rec.year or not rec.month:
                rec.historical_increase_ids = Inc
                continue
            start, end = rec._month_bounds()
            lines = Inc.search([
                ('employee_id', '=', rec.employee_id.id),
                ('date', '>=', start),
                ('date', '<=', end),
            ])
            rec.historical_increase_ids = lines

    @api.depends('historical_increase_ids')
    def _compute_historical_increase_count(self):
        for rec in self:
            rec.historical_increase_count = len(rec.historical_increase_ids)

    @api.depends('employee_id', 'year', 'month', 'amount_monthly_display')
    def _compute_month_comparison(self):
        for rec in self:
            rec.previous_month_display = False
            rec.delta_vs_previous = False
            if not rec.employee_id or not rec.year or not rec.month:
                continue
            d = date(rec.year, rec.month, 1) - relativedelta(months=1)
            prev = self.search([
                ('employee_id', '=', rec.employee_id.id),
                ('year', '=', d.year),
                ('month', '=', d.month),
            ], limit=1)
            if prev:
                rec.previous_month_display = prev.amount_monthly_display
                rec.delta_vs_previous = rec.amount_monthly_display - prev.amount_monthly_display

    def _month_bounds(self):
        self.ensure_one()
        last = monthrange(self.year, self.month)[1]
        return date(self.year, self.month, 1), date(self.year, self.month, last)

    @api.model
    def _commission_total_from_payslips(self, payslips):
        rules = self.env['hr.salary.rule'].search([('l10n_hn_counts_as_commission', '=', True)])
        codes = set(rules.mapped('code'))
        if not codes:
            return 0.0
        total = 0.0
        for slip in payslips:
            for line in slip.line_ids:
                if line.code in codes:
                    total += line.total or 0.0
        return total

    @api.model
    def _find_payslips_for_month(self, employee, year, month, states=None, company=None):
        if states is None:
            states = ('validated', 'paid')
        start_d, end_d = date(year, month, 1), date(year, month, monthrange(year, month)[1])
        domain = [
            ('employee_id', '=', employee.id),
            ('state', 'in', states),
            ('credit_note', '=', False),
            ('date_from', '<=', end_d),
            ('date_to', '>=', start_d),
        ]
        if company:
            domain.append(('company_id', '=', company.id))
        return self.env['hr.payslip'].search(domain)

    def _apply_snapshot_from_employee(self, employee):
        self.ensure_one()
        version = employee.current_version_id
        periodicity = version.periodicity if version else False
        self.periodicity_snapshot = periodicity or 'monthly'
        self.identification_snapshot = employee.identification_id
        self.hire_date_snapshot = employee._get_first_contract_date()
        self.department_id = employee.department_id
        self.job_id = employee.job_id

    @api.model
    def _values_from_payslips(self, employee, year, month, states=None, company=None):
        """Retorna dict para write/create desde recibos del mes."""
        payslips = self._find_payslips_for_month(employee, year, month, states=states, company=company)
        if not payslips:
            return None
        net_sum = sum(payslips.mapped('payslip_net_total'))
        comm = self._commission_total_from_payslips(payslips)
        vals = {
            'amount_net': net_sum,
            'amount_commission': comm,
            'payslip_ids': [(6, 0, payslips.ids)],
            'data_source': 'payslip',
        }
        return vals, payslips

    @api.model
    def regenerate_month(
        self, employee, year, month, states=None, company=None,
        overwrite_import=False,
    ):
        """Crea o actualiza un registro desde nómina para un empleado y mes."""
        company = company or employee.company_id
        if not company:
            raise UserError(_('El empleado %s no tiene compañía.') % employee.display_name)
        existing = self.search([
            ('employee_id', '=', employee.id),
            ('year', '=', year),
            ('month', '=', month),
        ], limit=1)
        if existing and existing.data_source in ('import', 'manual') and not overwrite_import:
            return existing

        found = self._values_from_payslips(employee, year, month, states=states, company=company)
        if not found:
            if existing and existing.data_source == 'payslip':
                existing.unlink()
            return self.env[self._name]

        vals, _noop = found
        if existing:
            if existing.data_source in ('import', 'manual'):
                vals['data_source'] = 'payslip'
            existing.write(vals)
            existing._apply_snapshot_from_employee(employee)
            return existing

        vals.update({
            'employee_id': employee.id,
            'company_id': company.id,
            'year': year,
            'month': month,
        })
        rec = self.create(vals)
        rec._apply_snapshot_from_employee(employee)
        return rec

    @api.model
    def regenerate_range(
        self, company, year_from, month_from, year_to, month_to,
        employee_ids=None, states=None, overwrite_import=False,
    ):
        """Regenera todos los meses en el rango [desde, hasta] inclusive."""
        domain = [('company_id', 'child_of', company.id)]
        if employee_ids is not None:
            domain.append(('id', 'in', employee_ids.ids))
        employees = self.env['hr.employee'].search(domain)
        start = date(year_from, month_from, 1)
        end = date(year_to, month_to, 1)
        cur = start
        processed = 0
        while cur <= end:
            y, m = cur.year, cur.month
            for emp in employees:
                rec = self.regenerate_month(
                    emp, y, m, states=states, company=company,
                    overwrite_import=overwrite_import,
                )
                if rec:
                    processed += 1
            cur += relativedelta(months=1)
        return processed
