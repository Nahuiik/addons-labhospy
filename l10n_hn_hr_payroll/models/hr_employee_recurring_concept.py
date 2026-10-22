# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, datetime
from dateutil.relativedelta import relativedelta


class HrEmployeeRecurringConcept(models.Model):
    """Employee Recurring Concept - Recurring income/deduction concepts"""
    _name = 'hr.employee.recurring.concept'
    _description = 'Employee Recurring Concept'
    _order = 'employee_id, date_start desc'
    
    employee_id = fields.Many2one('hr.employee', string='Employee', required=False, ondelete='cascade',
                                  help='Dejar vacío para crear un concepto compartido que puede asignarse a múltiples empleados')
    company_id = fields.Many2one('res.company', string='Company', 
                                compute='_compute_company_id', store=True,
                                help='Compañía del empleado o compañía actual si es concepto compartido')
    
    # Flag to identify shared concepts
    is_shared = fields.Boolean(string='Es Compartido', compute='_compute_is_shared', store=True,
                              help='Indica si este concepto es compartido (sin empleado específico)')
    
    @api.depends('employee_id')
    def _compute_company_id(self):
        """Compute company from employee or use current company"""
        for rec in self:
            if rec.employee_id:
                rec.company_id = rec.employee_id.company_id
            else:
                rec.company_id = self.env.company
    
    @api.depends('employee_id')
    def _compute_is_shared(self):
        """Compute if concept is shared (no employee assigned)"""
        for rec in self:
            rec.is_shared = not bool(rec.employee_id)
    
    # Field to select from existing recurring concepts (shows as "Concept Name" in the form)
    name_from_concept_id = fields.Many2one('hr.employee.recurring.concept',
                                         string='Concept Name',
                                         domain="['|', ('employee_id', '=', employee_id), ('employee_id', '=', False), ('id', '!=', id)]",
                                         help='Seleccione un concepto recurrente existente del mismo empleado o un concepto compartido, o escriba un nombre nuevo abajo')
    
    name = fields.Char(string='Nombre del Concepto', required=True,
                      help='Nombre del concepto. Se llena automáticamente al seleccionar un concepto recurrente existente arriba')
    
    # Code for salary rules (required for shared concepts, optional for employee-specific)
    code = fields.Char(string='Código', 
                      help='Código único para identificar este concepto en las reglas salariales. Requerido para conceptos compartidos. Se puede copiar desde otro concepto recurrente o especificar manualmente.')
    
    concept_type = fields.Selection([
        ('income', 'Income'),
        ('deduction', 'Deduction'),
    ], string='Type', required=True)
    
    amount_type = fields.Selection([
        ('fixed', 'Fixed Amount'),
        ('percentage', 'Percentage of Base Salary'),
    ], string='Amount Type', required=True, default='fixed')
    
    amount = fields.Float(string='Amount', digits=(12, 2), required=True,
                         help='Fixed amount or percentage value')
    
    # Loan fields
    is_loan = fields.Boolean(string='Is Loan', default=False)
    total_amount = fields.Float(
        string='Total Loan Amount',
        digits=(12, 2),
        compute='_compute_total_amount',
        store=True,
        readonly=False,
        help='Monto total del préstamo. Se calcula automáticamente como amount × installments cuando es préstamo con monto fijo.'
    )
    installments = fields.Integer(
        string='Number of Installments',
        default=1,
        compute='_compute_installments',
        store=True,
        readonly=False,
        help='Número de cuotas. Se calcula automáticamente desde fecha inicio, fecha fin y aplicar en quincena cuando están definidos.'
    )
    paid_installments = fields.Integer(
        string='Paid Installments',
        default=0,
        compute='_compute_paid_installments',
        store=True,
        readonly=False,
        inverse='_inverse_paid_installments',
        help='Cuotas pagadas = Cuotas iniciales pagadas + cuotas pagadas en nómina.'
    )
    initial_paid_installments = fields.Integer(
        string='Cuotas iniciales pagadas',
        default=0,
        help='Cuotas pagadas antes de que el empleado fuera incluido en la nómina (ej: préstamo iniciado en otro sistema).'
    )
    manual_paid_installments = fields.Integer(
        string='Cuotas pagadas en nómina',
        default=0,
        help='Cuotas pagadas mediante nómina (Marcar cuota pagada o deducciones aplicadas).'
    )
    remaining_amount = fields.Float(string='Remaining Amount', digits=(12, 2),
                                    compute='_compute_remaining_amount', store=True)
    
    # Dates
    date_start = fields.Date(string='Start Date', required=True, default=fields.Date.today)
    date_end = fields.Date(string='End Date')
    
    for_payroll = fields.Boolean(string='Para Planilla', default=False,
                                 help='Incluir en selector de conceptos de Beneficios/Deducciones en Planilla')

    # Trazabilidad: origen desde planilla BD (para deshacer de forma segura)
    payroll_sheet_line_bd_id = fields.Many2one('l10n.hn.payroll.line.bd', string='Origen Planilla BD',
                                               ondelete='set null', readonly=True,
                                               help='Línea de planilla que creó este concepto (para reversión)')

    # Biweekly application (only relevant for biweekly structures)
    apply_biweek = fields.Selection([
        ('both', 'Ambas Quincenas'),
        ('first', 'Primera Quincena (1-15)'),
        ('second', 'Segunda Quincena (16-fin)'),
    ], string='Aplicar en Quincena', default='both',
       help='Especifica en qué quincena aplicar este concepto cuando la estructura es quincenal. Para estructuras mensuales se ignora.')

    active = fields.Boolean(string='Active', default=True)
    
    # Applicability criteria (for shared concepts - replaces master concept functionality)
    applies_to_all = fields.Boolean(string='Aplica a Todos los Empleados', default=False,
                                    help='Si está marcado, este concepto puede asignarse a todos los empleados')
    department_ids = fields.Many2many('hr.department', string='Departamentos',
                                     help='Si no aplica a todos, especificar departamentos específicos')
    job_ids = fields.Many2many('hr.job', string='Puestos de Trabajo',
                              help='Si no aplica a todos, especificar puestos específicos')
    structure_type_ids = fields.Many2many('hr.payroll.structure.type', string='Tipos de Estructura',
                                         help='Tipos de estructura de nómina donde aplica este concepto')
    
    description = fields.Text(string='Descripción',
                             help='Descripción detallada del concepto')
    
    
    # Keep template_concept_id for backward compatibility but it's now redundant
    # name_from_concept_id serves the same purpose
    # Note: This field is hidden in views, not in the model definition
    template_concept_id = fields.Many2one('hr.employee.recurring.concept', 
                                         string='Copiar de Concepto Recurrente',
                                         domain="[('employee_id', '=', employee_id), ('id', '!=', id)]",
                                         help='Campo oculto para compatibilidad. Use name_from_concept_id en su lugar.')
    
    notes = fields.Text(string='Notes')
    
    @api.model
    def default_get(self, fields_list):
        """Set default employee_id from context"""
        res = super().default_get(fields_list)
        # Get employee_id from context if available (when creating from employee form)
        # If not in context, leave empty to allow creating shared concepts
        if 'default_employee_id' in self.env.context:
            res['employee_id'] = self.env.context['default_employee_id']
        return res
    
    @api.constrains('employee_id', 'name', 'code', 'applies_to_all', 'department_ids', 'job_ids')
    def _check_shared_concept(self):
        """Validate shared concepts"""
        for rec in self:
            if not rec.employee_id:  # Es concepto compartido
                # Shared concept must have a name and code
                if not rec.name:
                    raise ValidationError(_('Los conceptos compartidos deben tener un nombre.'))
                if not rec.code:
                    raise ValidationError(_('Los conceptos compartidos deben tener un código para las reglas salariales.'))
                
                # Validate applicability criteria
                if not rec.applies_to_all and not rec.department_ids and not rec.job_ids:
                    # Allow empty criteria - user can assign manually via wizard
                    pass
    
    def action_assign_to_employees(self):
        """Assign this shared recurring concept to multiple employees"""
        self.ensure_one()
        if self.employee_id:
            raise UserError(_('Este concepto ya está asignado a un empleado específico. Solo los conceptos compartidos pueden asignarse a múltiples empleados.'))
        
        if not self.active:
            raise UserError(_('El concepto debe estar activo para asignarlo a empleados.'))
        
        # Check if concept has applicability criteria for automatic assignment
        has_criteria = self.applies_to_all or self.department_ids or self.job_ids
        
        if has_criteria:
            # Automatic assignment based on criteria (like master concepts)
            return self._assign_by_criteria()
        else:
            # Manual selection via wizard
            return {
                'type': 'ir.actions.act_window',
                'name': _('Asignar Concepto a Empleados'),
                'res_model': 'hr.employee.recurring.concept.assign.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_concept_id': self.id,
                }
            }
    
    def _assign_by_criteria(self):
        """Assign concept to employees based on applicability criteria"""
        self.ensure_one()
        
        # Build domain for eligible employees
        domain = [
            ('active', '=', True),
        ]
        
        if not self.applies_to_all:
            if self.department_ids:
                domain.append(('department_id', 'in', self.department_ids.ids))
            if self.job_ids:
                domain.append(('job_id', 'in', self.job_ids.ids))
        
        employees = self.env['hr.employee'].search(domain)
        
        created_count = 0
        for employee in employees:
            # Check if employee already has this concept (by code)
            existing = self.env['hr.employee.recurring.concept'].search([
                ('employee_id', '=', employee.id),
                ('code', '=', self.code),
                ('active', '=', True),
            ])
            
            if not existing:
                # Check if employee's structure type matches
                v_sudo = employee.current_version_id.sudo() if employee.current_version_id else False
                if v_sudo and v_sudo.structure_type_id:
                    if self.structure_type_ids and v_sudo.structure_type_id.id not in self.structure_type_ids.ids:
                        continue
                
                # Create recurring concept for employee
                # For loans, don't copy total_amount from shared concept - each employee can have different amount
                vals = {
                    'employee_id': employee.id,
                    'name': self.name,
                    'code': self.code,
                    'concept_type': self.concept_type,
                    'amount_type': self.amount_type,
                    'amount': self.amount,
                    'is_loan': self.is_loan,
                    'installments': self.installments if self.is_loan else 1,
                    'total_amount': self.total_amount if (self.is_loan and self.total_amount > 0) else 0.0,
                    'date_start': self.date_start,
                    'date_end': self.date_end,
                    'apply_biweek': self.apply_biweek,
                    'active': True,
                }
                self.env['hr.employee.recurring.concept'].create(vals)
                created_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Conceptos Asignados'),
                'message': _('Se asignaron %d conceptos a empleados elegibles basados en los criterios de aplicabilidad.') % created_count,
                'type': 'success',
            }
        }
    
    @api.onchange('name_from_concept_id')
    def _onchange_name_from_concept_id(self):
        """Auto-fill all fields when selecting an existing recurring concept"""
        if self.name_from_concept_id:
            template = self.name_from_concept_id
            self.name = template.name
            self.code = template.code  # Copy code from template
            self.concept_type = template.concept_type
            self.amount_type = template.amount_type
            self.amount = template.amount
            self.is_loan = template.is_loan
            if template.is_loan:
                self.installments = template.installments
                self.total_amount = template.total_amount
            
            # Copy applicability criteria if copying from shared concept to shared concept
            if not self.employee_id and not template.employee_id:
                self.applies_to_all = template.applies_to_all
                self.department_ids = template.department_ids
                self.job_ids = template.job_ids
                self.structure_type_ids = template.structure_type_ids
                self.description = template.description
            
            # Copy biweekly application setting
            self.apply_biweek = template.apply_biweek
            
            # Don't copy dates, notes, or paid_installments as those are specific to each concept
    
    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        """Clear concept selections when employee changes"""
        if self.employee_id:
            # Reset name_from_concept_id if it belongs to a different employee
            if self.name_from_concept_id and self.name_from_concept_id.employee_id != self.employee_id:
                self.name_from_concept_id = False
            # Reset template_concept_id if it belongs to a different employee
            if self.template_concept_id and self.template_concept_id.employee_id != self.employee_id:
                self.template_concept_id = False
    
    def _calculate_loan_end_date(self, start, installments, apply_biweek):
        """Calcular fecha fin del préstamo dado fecha inicio, cuotas y quincena.

        Itera quincenas hacia adelante desde *start* y devuelve la fecha de
        cierre de la última quincena cuando se alcanza el número de cuotas.
        """
        if not start or not installments or installments <= 0:
            return False
        apply = apply_biweek or 'both'
        count = 0
        current = date(start.year, start.month, 1)
        last_period_end = None
        max_months = installments * 2 + 12

        for _ in range(max_months):
            first_biweek_end = date(current.year, current.month, 15)
            month_end = current + relativedelta(months=1) - relativedelta(days=1)

            if apply in ('both', 'first') and first_biweek_end >= start:
                count += 1
                last_period_end = first_biweek_end
                if count >= installments:
                    break

            if apply in ('both', 'second') and month_end >= start:
                count += 1
                last_period_end = month_end
                if count >= installments:
                    break

            current += relativedelta(months=1)

        return last_period_end

    @api.onchange('is_loan', 'installments', 'apply_biweek', 'date_start', 'initial_paid_installments')
    def _onchange_loan_compute_end_date(self):
        """Para préstamos: calcular date_end desde cuotas restantes, apply_biweek y date_start."""
        if not self.is_loan or not self.date_start or not self.installments or self.installments <= 0:
            return
        remaining = self.installments - (self.paid_installments or 0)
        if remaining <= 0:
            return
        end = self._calculate_loan_end_date(self.date_start, remaining, self.apply_biweek)
        if end:
            self.date_end = end

    @api.depends('date_start', 'date_end', 'apply_biweek', 'is_loan')
    def _compute_installments(self):
        """Calcular cuotas desde fecha inicio, fecha fin y aplicar en quincena.

        Para préstamos (is_loan=True) el usuario ingresa las cuotas directamente
        y date_end se calcula desde ellas (vía onchange); no se sobreescribe aquí.

        Para conceptos regulares (no préstamo) con nómina quincenal Honduras:
        - both: 2 cuotas por mes (primera y segunda quincena)
        - first: 1 cuota por mes (solo días 1-15)
        - second: 1 cuota por mes (solo días 16-fin)
        """
        for rec in self:
            if rec.is_loan:
                continue

            if not rec.date_start or not rec.date_end or not rec.apply_biweek:
                rec.installments = 1
                continue
            if rec.date_end < rec.date_start:
                rec.installments = 1
                continue

            count = 0
            start = rec.date_start
            end = rec.date_end

            current = date(start.year, start.month, 1)
            end_month_first = date(end.year, end.month, 1)

            while current <= end_month_first:
                first_biweek_start = current
                first_biweek_end = date(current.year, current.month, 15)
                second_biweek_start = date(current.year, current.month, 16)
                second_biweek_end = current + relativedelta(months=1) - relativedelta(days=1)

                def overlaps(period_start, period_end):
                    return not (period_end < start or period_start > end)

                if rec.apply_biweek in ('both', 'first'):
                    if overlaps(first_biweek_start, first_biweek_end):
                        count += 1
                if rec.apply_biweek in ('both', 'second'):
                    if overlaps(second_biweek_start, second_biweek_end):
                        count += 1

                current += relativedelta(months=1)

            rec.installments = max(1, count)

    @api.depends('amount', 'installments', 'amount_type', 'is_loan')
    def _compute_total_amount(self):
        """Calcular monto total desde amount × installments.

        Para préstamos con monto fijo: total_amount = amount × installments.
        Para préstamos con porcentaje: se requiere salario del empleado; si no hay
        empleado o contrato, total_amount queda en 0 (ingresar manualmente si aplica).
        """
        for rec in self:
            if not rec.is_loan or not rec.installments:
                rec.total_amount = 0.0
                continue
            if rec.amount_type == 'fixed':
                rec.total_amount = rec.amount * rec.installments
            elif rec.amount_type == 'percentage' and rec.employee_id:
                version = rec.employee_id.current_version_id.sudo() if rec.employee_id.current_version_id else False
                if version and version.wage:
                    wage = version.wage
                    periodicity = version.periodicity or 'monthly'
                    if periodicity in ('biweekly', 'bi-weekly'):
                        amount_per_period = (wage / 2.0) * (rec.amount / 100.0)
                    elif periodicity == 'weekly':
                        amount_per_period = (wage / 4.33) * (rec.amount / 100.0)
                    else:
                        amount_per_period = wage * (rec.amount / 100.0)
                    rec.total_amount = round(amount_per_period * rec.installments, 2)
                else:
                    rec.total_amount = 0.0
            else:
                rec.total_amount = 0.0

    @api.depends('initial_paid_installments', 'manual_paid_installments')
    def _compute_paid_installments(self):
        """Cuotas pagadas = cuotas iniciales (antes de nómina) + cuotas pagadas en nómina."""
        for rec in self:
            rec.paid_installments = rec.initial_paid_installments + rec.manual_paid_installments

    def _inverse_paid_installments(self):
        """Al escribir paid_installments, ajustar manual_paid_installments."""
        for rec in self:
            rec.manual_paid_installments = max(0, rec.paid_installments - rec.initial_paid_installments)

    @api.depends('total_amount', 'amount', 'paid_installments', 'installments')
    def _compute_remaining_amount(self):
        for rec in self:
            if rec.is_loan and rec.total_amount > 0:
                paid = rec.amount * rec.paid_installments
                rec.remaining_amount = rec.total_amount - paid
            else:
                rec.remaining_amount = 0.0

    @api.constrains('amount_type', 'amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount_type == 'percentage' and (rec.amount < 0 or rec.amount > 100):
                raise ValidationError(_('El porcentaje debe estar entre 0 y 100.'))
    
    @api.constrains('is_loan', 'total_amount', 'installments', 'employee_id')
    def _check_loan(self):
        for rec in self:
            if rec.is_loan:
                # total_amount opcional en conceptos compartidos (plantilla): crear regla y asignar a múltiples empleados
                # con montos distintos. En conceptos por empleado también puede dejarse vacío al asignar; se completa después.
                if not rec.installments or rec.installments <= 0:
                    raise ValidationError(_('Debe especificar el número de cuotas.'))
    
    def action_mark_paid(self):
        """Marcar cuota como pagada (incrementa manual_paid_installments)"""
        self.ensure_one()
        if not self.is_loan:
            raise UserError(_('Solo se pueden marcar cuotas para conceptos de préstamo.'))
        if self.paid_installments >= self.installments:
            raise UserError(_('Todas las cuotas ya han sido pagadas.'))
        self.manual_paid_installments += 1
        if self.manual_paid_installments >= self.installments:
            self.active = False
