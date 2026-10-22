# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrEmployeeExportExcelWizard(models.TransientModel):
    """Wizard para exportar empleados a Excel con filtros."""
    _name = 'hr.employee.export.excel.wizard'
    _description = 'Export Employees to Excel Wizard'

    filter_type = fields.Selection([
        ('all', 'Todos los empleados'),
        ('department', 'Por departamento'),
        ('manager', 'Por jefe del empleado'),
    ], string='Filtrar por', default='all', required=True)

    department_id = fields.Many2one(
        'hr.department',
        string='Departamento',
        help='Solo se exportarán empleados de este departamento.',
    )
    manager_id = fields.Many2one(
        'hr.employee',
        string='Jefe inmediato',
        help='Solo se exportarán empleados que reporten a este jefe.',
    )

    expiring_this_month = fields.Boolean(
        string='Solo contratos que vencen este mes',
        default=False,
        help='Exportar únicamente empleados cuyo contrato vence en el mes actual.',
    )

    export_type = fields.Selection([
        ('registro', 'Registro de contratos'),
        ('empleados', 'Listado de empleados'),
    ], string='Tipo de exportación', default='registro', required=True)

    @api.onchange('filter_type')
    def _onchange_filter_type(self):
        """Limpiar campos cuando cambia el tipo de filtro."""
        self.department_id = False
        self.manager_id = False

    def _get_employees(self):
        """Obtiene los empleados según el filtro seleccionado."""
        self.ensure_one()
        domain = [('company_id', 'in', self.env.companies.ids)]
        if self.filter_type == 'department':
            if not self.department_id:
                raise UserError(_('Debe seleccionar un departamento.'))
            domain.append(('department_id', '=', self.department_id.id))
        elif self.filter_type == 'manager':
            if not self.manager_id:
                raise UserError(_('Debe seleccionar un jefe inmediato.'))
            domain.append(('parent_id', '=', self.manager_id.id))

        if self.expiring_this_month:
            today = date.today()
            start_of_month = today.replace(day=1)
            end_of_month = start_of_month + relativedelta(months=1) - relativedelta(days=1)
            domain.extend([
                ('current_contract_date_end', '!=', False),
                ('current_contract_date_end', '>=', start_of_month),
                ('current_contract_date_end', '<=', end_of_month),
            ])

        return self.env['hr.employee'].search(domain, order='name')

    def action_export(self):
        """Ejecuta la exportación según el tipo seleccionado."""
        self.ensure_one()
        employees = self._get_employees()
        if not employees:
            raise UserError(_('No hay empleados que coincidan con el filtro seleccionado.'))

        if self.export_type == 'registro':
            return employees.with_context(active_ids=employees.ids).action_export_registro_contratos()
        return employees.with_context(active_ids=employees.ids).action_export_employees_excel()
