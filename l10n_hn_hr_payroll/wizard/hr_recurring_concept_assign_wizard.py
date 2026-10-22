# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrRecurringConceptAssignWizard(models.TransientModel):
    """Wizard to assign shared recurring concept to multiple employees"""
    _name = 'hr.employee.recurring.concept.assign.wizard'
    _description = 'Assign Recurring Concept to Employees Wizard'
    
    concept_id = fields.Many2one('hr.employee.recurring.concept', string='Concepto', required=True,
                                 domain=[('employee_id', '=', False)],
                                 help='Concepto compartido a asignar')
    employee_ids = fields.Many2many('hr.employee', string='Empleados', required=True,
                                   help='Empleados a los que se asignará el concepto')
    date_start = fields.Date(string='Fecha de Inicio', required=True, default=fields.Date.today,
                            help='Fecha de inicio del concepto para los empleados seleccionados')
    date_end = fields.Date(string='Fecha de Fin',
                          help='Fecha de fin del concepto (opcional)')
    
    @api.model
    def default_get(self, fields_list):
        """Set default concept from context"""
        res = super().default_get(fields_list)
        if 'default_concept_id' in self.env.context:
            res['concept_id'] = self.env.context['default_concept_id']
        return res
    
    def action_assign(self):
        """Assign concept to selected employees"""
        self.ensure_one()
        if not self.concept_id:
            raise UserError(_('Debe seleccionar un concepto.'))
        
        if self.concept_id.employee_id:
            raise UserError(_('El concepto seleccionado no es compartido. Solo se pueden asignar conceptos compartidos.'))
        
        if not self.employee_ids:
            raise UserError(_('Debe seleccionar al menos un empleado.'))
        
        created_count = 0
        skipped_count = 0
        for employee in self.employee_ids:
            # Check if employee already has this concept (by code)
            existing = self.env['hr.employee.recurring.concept'].search([
                ('employee_id', '=', employee.id),
                ('code', '=', self.concept_id.code),
                ('active', '=', True),
            ])
            
            if existing:
                skipped_count += 1
                continue
            
            # Check if employee's structure type matches (if structure_type_ids is set)
            if self.concept_id.structure_type_ids:
                version = employee.current_version_id.sudo() if employee.current_version_id else False
                if not version or not version.structure_type_id:
                    skipped_count += 1
                    continue
                if version.structure_type_id.id not in self.concept_id.structure_type_ids.ids:
                    skipped_count += 1
                    continue
            
            # Create recurring concept for employee
            # For loans, don't copy total_amount from shared concept - each employee can have different amount
            vals = {
                'employee_id': employee.id,
                'name': self.concept_id.name,
                'code': self.concept_id.code,
                'concept_type': self.concept_id.concept_type,
                'amount_type': self.concept_id.amount_type,
                'amount': self.concept_id.amount,
                'is_loan': self.concept_id.is_loan,
                'installments': self.concept_id.installments if self.concept_id.is_loan else 1,
                'total_amount': self.concept_id.total_amount if (self.concept_id.is_loan and self.concept_id.total_amount > 0) else 0.0,
                'date_start': self.date_start,
                'date_end': self.date_end,
                'apply_biweek': self.concept_id.apply_biweek,
                'active': True,
            }
            self.env['hr.employee.recurring.concept'].create(vals)
            created_count += 1
        
        message = _('Se asignó el concepto "%s" a %d empleado(s).') % (self.concept_id.name, created_count)
        if skipped_count > 0:
            message += _(' %d empleado(s) fueron omitidos (ya tienen el concepto o no cumplen los criterios).') % skipped_count
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Conceptos Asignados'),
                'message': message,
                'type': 'success',
            }
        }
