# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class HrSalaryIncrease(models.Model):
    """Salary Increase - Individual or mass salary increases"""
    _name = 'hr.salary.increase'
    _description = 'Salary Increase'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    
    name = fields.Char(string='Nombre', required=True, tracking=True)
    date = fields.Date(string='Fecha efectiva', required=True, default=fields.Date.today, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    
    increase_type = fields.Selection([
        ('individual', 'Individual'),
        ('department', 'By Department'),
        ('all', 'All Employees'),
    ], string='Increase Type', required=True, default='individual')
    
    department_id = fields.Many2one('hr.department', string='Department',
                                     help='Required if increase type is "By Department"')
    
    employee_ids = fields.Many2many('hr.employee', string='Employees',
                                    help='Required if increase type is "Individual"')
    
    calculation_method = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ], string='Calculation Method', compute='_compute_calculation_method', store=True, readonly=False,
       help='Automatically determined based on which field has a value')
    
    percentage = fields.Float(string='Percentage (%)', digits=(5, 2),
                              help='Percentage increase (e.g., 10 for 10%)')
    
    fixed_amount = fields.Float(string='Fixed Amount', digits=(12, 2),
                                help='Fixed amount increase')
    
    line_ids = fields.One2many('hr.employee.salary.line', 'increase_id', string='Salary Lines')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('validated', 'Validated'),
    ], string='State', default='draft', required=True, tracking=True)
    
    date_validated = fields.Datetime(string='Fecha de validación', readonly=True)
    
    effective_period_id = fields.Many2one(
        'l10n.hn.payroll.period',
        string='Quincena efectiva',
        compute='_compute_effective_period',
        store=True,
        help='Quincena en la que el aumento se reflejará en el recibo de nómina.',
    )
    effective_period_warning = fields.Char(
        string='Aviso quincena',
        compute='_compute_effective_period',
        store=True,
    )
    
    notes = fields.Text(string='Notes')
    
    @api.depends('date', 'company_id')
    def _compute_effective_period(self):
        for rec in self:
            if not rec.date:
                rec.effective_period_id = False
                rec.effective_period_warning = ''
                continue
            period = rec.env['l10n.hn.payroll.period'].search([
                ('date_start', '<=', rec.date),
                ('date_end', '>=', rec.date),
                ('company_id', '=', rec.company_id.id),
            ], limit=1)
            rec.effective_period_id = period
            if period:
                rec.effective_period_warning = _(
                    'El aumento se verá reflejado en el recibo de nómina de la quincena: %s'
                ) % period.name
            else:
                rec.effective_period_warning = _(
                    'No se encontró una quincena configurada para la fecha efectiva. '
                    'Verifique que exista el período en Nómina → Quincenas.'
                )
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                date_str = vals.get('date', fields.Date.today)
                if isinstance(date_str, str):
                    date_str = fields.Date.from_string(date_str)
                vals['name'] = _('Aumento Salarial - %s') % date_str
        return super().create(vals_list)
    
    @api.depends('percentage', 'fixed_amount')
    def _compute_calculation_method(self):
        """Compute calculation method based on which field has a value"""
        for rec in self:
            if rec.percentage:
                rec.calculation_method = 'percentage'
            elif rec.fixed_amount:
                rec.calculation_method = 'fixed'
            elif not rec.calculation_method:
                # Default to percentage if neither has value yet
                rec.calculation_method = 'percentage'
    
    @api.constrains('increase_type', 'department_id')
    def _check_required_fields(self):
        for rec in self:
            if rec.increase_type == 'department' and not rec.department_id:
                raise ValidationError(_('Debe seleccionar un departamento para aumentos por departamento.'))
    
    @api.constrains('percentage', 'fixed_amount', 'increase_type')
    def _check_calculation(self):
        for rec in self:
            # En incremento individual no es obligatorio; en otros tipos sí
            if rec.increase_type == 'individual':
                continue
            if not rec.percentage and not rec.fixed_amount:
                raise ValidationError(_('Debe especificar al menos un porcentaje o un monto fijo de aumento.'))
    
    def action_get_employees(self):
        """Get employees based on increase type"""
        self.ensure_one()
        employees = self.env['hr.employee']
        
        if self.increase_type == 'all':
            employees = self.env['hr.employee'].search([
                ('active', '=', True),
                ('company_id', '=', self.company_id.id)
            ])
        elif self.increase_type == 'department' and self.department_id:
            employees = self.env['hr.employee'].search([
                ('active', '=', True),
                ('department_id', '=', self.department_id.id),
                ('company_id', '=', self.company_id.id)
            ])
        elif self.increase_type == 'individual':
            employees = self.employee_ids.filtered(lambda e: e.active)
        
        # Create lines for each employee
        existing_employee_ids = self.line_ids.mapped('employee_id').ids
        for employee in employees:
            if employee.id not in existing_employee_ids:
                v = employee.current_version_id.sudo() if employee.current_version_id else False
                current_wage = v.wage or 0.0 if v else 0.0
                current_dept = v.department_id if v else False
                current_job = v.job_id if v else False
                if self.percentage:
                    new_wage = current_wage * (1 + self.percentage / 100.0)
                elif self.fixed_amount:
                    new_wage = current_wage + self.fixed_amount
                else:
                    new_wage = current_wage
                self.env['hr.employee.salary.line'].create({
                    'increase_id': self.id,
                    'employee_id': employee.id,
                    'current_wage': current_wage,
                    'new_wage': new_wage,
                    'current_department_id': current_dept.id if current_dept else False,
                    'new_department_id': current_dept.id if current_dept else False,
                    'current_job_id': current_job.id if current_job else False,
                    'new_job_id': current_job.id if current_job else False,
                })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Empleados Obtenidos'),
                'message': _('Se obtuvieron %d empleados.') % len(employees),
                'type': 'success',
            }
        }
    
    def action_validate(self):
        """Validate and apply salary increases"""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Debe obtener los empleados primero.'))
        
        if self.state != 'draft':
            raise UserError(_('Solo se pueden validar aumentos en estado borrador.'))
        
        # Validar que al menos una línea tenga algún cambio (salario, departamento o puesto)
        def _has_change(l):
            wage_change = l.increase_amount != 0
            dept_change = (l.new_department_id or l.current_department_id) and l.new_department_id != l.current_department_id
            job_change = (l.new_job_id or l.current_job_id) and l.new_job_id != l.current_job_id
            return wage_change or dept_change or job_change

        lines_with_changes = self.line_ids.filtered(_has_change)
        if not lines_with_changes:
            if self.increase_type != 'individual' and not self.percentage and not self.fixed_amount:
                raise UserError(_('Debe especificar al menos un porcentaje o monto fijo de aumento, o editar en las líneas: nuevo salario, nuevo departamento o nuevo puesto.'))
            raise UserError(_('Debe haber al menos una línea con cambio. Edite el nuevo salario, departamento o puesto en las líneas.'))

        for line in self.line_ids:
            if not line.employee_id.current_version_id:
                raise UserError(_('El empleado %s no tiene una versión de contrato activa.') % line.employee_id.name)


            inc_pct = ((line.new_wage / line.current_wage - 1) * 100) if line.current_wage > 0 else 0
            self.env['hr.historical.salary.increase'].create({
                'employee_id': line.employee_id.id,
                'increase_id': self.id,
                'date': self.date,
                'previous_wage': line.current_wage,
                'new_wage': line.new_wage,
                'increase_amount': line.increase_amount,
                'increase_percentage': inc_pct,
                'previous_department_id': line.current_department_id.id if line.current_department_id else False,
                'new_department_id': line.new_department_id.id if line.new_department_id else False,
                'previous_job_id': line.current_job_id.id if line.current_job_id else False,
                'new_job_id': line.new_job_id.id if line.new_job_id else False,
            })

            version_vals = {
                'wage': line.new_wage,
                'department_id': line.new_department_id.id if line.new_department_id else False,
                'job_id': line.new_job_id.id if line.new_job_id else False,
            }
            line.employee_id.current_version_id.sudo().with_context(from_salary_increase=True).write(version_vals)
        
        self.write({
            'state': 'validated',
            'date_validated': fields.Datetime.now(),
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Aumentos Validados'),
                'message': _('Se aplicaron %d aumentos salariales correctamente.') % len(self.line_ids),
                'type': 'success',
            }
        }
    
    def action_set_draft(self):
        """Revert to draft and restore previous wages"""
        self.ensure_one()
        if self.state != 'validated':
            raise UserError(_('Solo se pueden revertir aumentos validados.'))
        
        for line in self.line_ids:
            if line.employee_id.current_version_id:
                line.employee_id.current_version_id.sudo().with_context(from_salary_increase=True).write({
                    'wage': line.current_wage,
                    'department_id': line.current_department_id.id if line.current_department_id else False,
                    'job_id': line.current_job_id.id if line.current_job_id else False,
                })
        
        # Delete historical records
        self.env['hr.historical.salary.increase'].search([
            ('increase_id', '=', self.id)
        ]).unlink()
        
        self.write({
            'state': 'draft',
            'date_validated': False,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Aumentos Revertidos'),
                'message': _('Los aumentos han sido revertidos a estado borrador y los salarios restaurados.'),
                'type': 'info',
            }
        }


class HrEmployeeSalaryLine(models.Model):
    """Employee Salary Line - Individual salary increase, department or job change"""
    _name = 'hr.employee.salary.line'
    _description = 'Employee Salary Line'
    _order = 'employee_id'
    
    increase_id = fields.Many2one('hr.salary.increase', string='Salary Increase', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    
    # Salario
    current_wage = fields.Float(string='Salario actual', digits=(12, 2), readonly=True)
    new_wage = fields.Float(string='Nuevo salario', digits=(12, 2), required=True)
    increase_amount = fields.Float(string='Monto aumento', digits=(12, 2), compute='_compute_increase_amount', store=True)
    increase_percentage = fields.Float(string='% aumento', digits=(5, 2),
                                       compute='_compute_increase_percentage', store=True)
    
    # Departamento
    current_department_id = fields.Many2one('hr.department', string='Departamento actual', readonly=True)
    new_department_id = fields.Many2one('hr.department', string='Nuevo departamento')
    
    # Puesto
    current_job_id = fields.Many2one('hr.job', string='Puesto actual', readonly=True)
    new_job_id = fields.Many2one('hr.job', string='Nuevo puesto')
    
    @api.depends('current_wage', 'new_wage')
    def _compute_increase_amount(self):
        for rec in self:
            rec.increase_amount = rec.new_wage - rec.current_wage
    
    @api.depends('current_wage', 'new_wage')
    def _compute_increase_percentage(self):
        for rec in self:
            if rec.current_wage > 0:
                rec.increase_percentage = ((rec.new_wage / rec.current_wage - 1) * 100)
            else:
                rec.increase_percentage = 0.0
    
    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id and self.employee_id.current_version_id:
            v = self.employee_id.current_version_id.sudo()
            self.current_wage = v.wage or 0.0
            self.current_department_id = v.department_id
            self.current_job_id = v.job_id
            self.new_department_id = v.department_id
            self.new_job_id = v.job_id
            if self.increase_id:
                if self.increase_id.percentage:
                    self.new_wage = self.current_wage * (1 + self.increase_id.percentage / 100.0)
                elif self.increase_id.fixed_amount:
                    self.new_wage = self.current_wage + self.increase_id.fixed_amount


class HrHistoricalSalaryIncrease(models.Model):
    """Historical Salary Increase - Track salary, department and job changes"""
    _name = 'hr.historical.salary.increase'
    _description = 'Historical Salary Increase'
    _order = 'date desc, id desc'
    
    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True, ondelete='cascade')
    increase_id = fields.Many2one('hr.salary.increase', string='Aumento', required=True, ondelete='cascade')
    date = fields.Date(string='Fecha', required=True)
    
    previous_wage = fields.Float(string='Salario anterior', digits=(12, 2))
    new_wage = fields.Float(string='Salario nuevo', digits=(12, 2))
    increase_amount = fields.Float(string='Monto aumento', digits=(12, 2))
    increase_percentage = fields.Float(string='% aumento', digits=(5, 2))
    
    previous_department_id = fields.Many2one('hr.department', string='Departamento anterior')
    new_department_id = fields.Many2one('hr.department', string='Departamento nuevo')
    previous_job_id = fields.Many2one('hr.job', string='Puesto anterior')
    new_job_id = fields.Many2one('hr.job', string='Puesto nuevo')
    
    notes = fields.Text(string='Notas', related='increase_id.notes', readonly=True)
