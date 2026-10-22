# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrEmployeeRehireWizard(models.TransientModel):
    _name = 'l10n.hn.employee.rehire.wizard'
    _description = 'Asistente de recontratación'

    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', required=True, readonly=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', related='employee_id.company_id')
    currency_id = fields.Many2one('res.currency', related='employee_id.currency_id')

    contract_date_start = fields.Date(string='Inicio de contrato', required=True)
    contract_date_end = fields.Date(string='Fin de contrato')
    wage = fields.Monetary(string='Salario', required=True, currency_field='currency_id')
    department_id = fields.Many2one(
        'hr.department', string='Departamento', required=True, check_company=True)
    job_id = fields.Many2one('hr.job', string='Puesto de trabajo', check_company=True)
    parent_id = fields.Many2one(
        'hr.employee',
        string='Jefe inmediato',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        check_company=True,
    )
    coach_id = fields.Many2one(
        'hr.employee',
        string='Mentor',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        check_company=True,
    )
    resource_calendar_id = fields.Many2one(
        'resource.calendar',
        string='Horario de trabajo',
        check_company=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    contract_type_id = fields.Many2one(
        'hr.contract.type', string='Tipo de contrato', groups='hr.group_hr_manager')
    structure_type_id = fields.Many2one(
        'hr.payroll.structure.type',
        string='Tipo de estructura salarial',
        groups='hr.group_hr_manager',
    )
    hr_responsible_id = fields.Many2one(
        'res.users',
        string='Responsable de contratos',
        groups='hr.group_hr_manager',
        domain="[('share', '=', False)]",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        emp_id = self.env.context.get('default_employee_id') or self.env.context.get('active_id')
        if not emp_id:
            return res
        emp = self.env['hr.employee'].with_context(active_test=False).browse(emp_id).exists()
        if not emp:
            return res
        vals = {
            'employee_id': emp.id,
            'contract_date_start': fields.Date.today(),
            'contract_date_end': False,
            'wage': emp.wage or 0.0,
            'department_id': emp.department_id.id if emp.department_id else False,
            'job_id': emp.job_id.id if emp.job_id else False,
            'parent_id': emp.parent_id.id if emp.parent_id else False,
            'coach_id': emp.coach_id.id if emp.coach_id else False,
        }
        cv = emp.sudo().current_version_id
        if cv:
            vals['wage'] = cv.wage or vals['wage']
            if cv.department_id:
                vals['department_id'] = cv.department_id.id
            if cv.job_id:
                vals['job_id'] = cv.job_id.id
            vals['resource_calendar_id'] = cv.resource_calendar_id.id if cv.resource_calendar_id else False
            vals['contract_type_id'] = cv.contract_type_id.id if cv.contract_type_id else False
            vals['structure_type_id'] = cv.structure_type_id.id if cv.structure_type_id else False
            vals['hr_responsible_id'] = cv.hr_responsible_id.id if cv.hr_responsible_id else False
        for fname, value in vals.items():
            if fname in fields_list:
                res[fname] = value
        return res

    def action_apply(self):
        self.ensure_one()
        emp = self.employee_id.with_context(active_test=False)
        if not emp.exists():
            raise UserError(_('Empleado no válido.'))
        if emp.active:
            raise UserError(_('Este empleado ya está activo; no aplica la recontratación.'))

        clash = self.env['hr.version'].search([
            ('employee_id', '=', emp.id),
            ('date_version', '=', self.contract_date_start),
            ('active', '=', True),
        ], limit=1)
        if clash:
            raise UserError(_(
                'Ya existe una versión de contrato activa con la misma fecha efectiva (%(date)s). '
                'Cambie la fecha de inicio o ajuste la versión existente.',
                date=self.contract_date_start,
            ))

        version_vals = {
            'employee_id': emp.id,
            'contract_date_start': self.contract_date_start,
            'contract_date_end': self.contract_date_end or False,
            'date_version': self.contract_date_start,
            'wage': self.wage,
            'department_id': self.department_id.id,
            'job_id': self.job_id.id if self.job_id else False,
        }
        if self.resource_calendar_id:
            version_vals['resource_calendar_id'] = self.resource_calendar_id.id
        if self.contract_type_id:
            version_vals['contract_type_id'] = self.contract_type_id.id
        if self.structure_type_id:
            version_vals['structure_type_id'] = self.structure_type_id.id
        if self.hr_responsible_id:
            version_vals['hr_responsible_id'] = self.hr_responsible_id.id

        self.env['hr.version'].create(version_vals)
        emp.write({
            'parent_id': self.parent_id.id if self.parent_id else False,
            'coach_id': self.coach_id.id if self.coach_id else False,
            'include_in_current_payroll': False,
        })
        emp.action_unarchive()
        return {
            'type': 'ir.actions.act_window',
            'name': emp.display_name,
            'res_model': 'hr.employee',
            'res_id': emp.id,
            'view_mode': 'form',
            'target': 'current',
        }
