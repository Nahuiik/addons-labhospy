# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

import base64
from datetime import date
from io import BytesIO

from odoo import _, api, fields, models
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class HnVacationStatusReportWizard(models.TransientModel):
    _name = 'hn.vacation.status.report.wizard'
    _description = 'Exportar Estatus Vacaciones a Excel'

    report_type = fields.Selection([
        ('detail', 'Detalle todos empleados'),
        ('department', 'Por Departamento'),
        ('project', 'Por Proyecto/Asignación'),
    ], string='Tipo de Reporte', default='detail', required=True)

    only_with_plan = fields.Boolean(
        'Solo empleados con plan de acumulación',
        default=True,
        help='Incluir únicamente empleados que tengan plan de vacaciones asignado.',
    )
    only_with_contract = fields.Boolean(
        'Solo empleados con contrato vigente',
        default=True,
        help='Incluir únicamente empleados con contrato vigente (fecha inicio y sin fin o fin >= hoy).',
    )
    sort_by = fields.Selection([
        ('department', 'Departamento'),
        ('employee', 'Empleado'),
        ('period', 'Período inicio'),
    ], string='Ordenar por', default='department', required=True)

    company_ids = fields.Many2many(
        'res.company',
        'hn_vacation_status_wizard_company_rel',
        'wizard_id', 'company_id',
        string='Compañías',
        help='Dejar vacío para todas las compañías.',
    )
    department_ids = fields.Many2many(
        'hr.department',
        'hn_vacation_status_wizard_department_rel',
        'wizard_id', 'department_id',
        string='Departamentos',
        help='Dejar vacío para todos los departamentos.',
    )
    employee_ids = fields.Many2many(
        'hr.employee',
        'hn_vacation_status_wizard_employee_rel',
        'wizard_id', 'employee_id',
        string='Empleados',
        help='Dejar vacío para todos los empleados.',
    )
    project_available = fields.Boolean(
        compute='_compute_project_available',
        string='Módulo project instalado',
    )

    @api.depends()
    def _compute_project_available(self):
        for wiz in self:
            wiz.project_available = bool(
                self.env['ir.module.module'].search([
                    ('name', '=', 'project'),
                    ('state', '=', 'installed'),
                ])
            )

    def _project_available(self):
        self.ensure_one()
        return self.project_available

    def _get_libro_domain(self):
        """Construye el domain base para buscar en gn.hn.vacation.libro."""
        self.ensure_one()
        domain = []
        if self.company_ids:
            domain.append(('company_id', 'in', self.company_ids.ids))
        if self.department_ids:
            domain.append(('department_id', 'in', self.department_ids.ids))
        if self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))
        return domain

    def _get_sort_order(self):
        """Retorna el order string según sort_by."""
        self.ensure_one()
        order_map = {
            'department': 'department_id, employee_name, period_start desc',
            'employee': 'employee_name, period_start desc',
            'period': 'period_start desc, employee_name',
        }
        return order_map.get(self.sort_by, 'department_id, employee_name')

    def _get_filtered_records(self):
        """Obtiene registros del libro aplicando filtros Python."""
        self.ensure_one()
        Libro = self.env['gn.hn.vacation.libro']
        domain = self._get_libro_domain()
        if self.only_with_contract:
            domain.append(('contract_date_start', '!=', False))
        records = Libro.search(domain, order=self._get_sort_order())
        if self.only_with_plan or self.only_with_contract:
            filtered = self.env['gn.hn.vacation.libro']
            today = date.today()
            for rec in records:
                emp = rec.employee_id
                if not emp:
                    continue
                if self.only_with_plan:
                    plan = emp.hn_vacation_plan_id or emp._get_default_hn_vacation_plan()
                    if not plan:
                        continue
                if self.only_with_contract:
                    if hasattr(emp, 'contract_date_end') and emp.contract_date_end:
                        if emp.contract_date_end < today:
                            continue
                filtered |= rec
            records = filtered
        if self.report_type == 'project' and self._project_available():
            records = self._filter_by_project(records)
        return records

    def _filter_by_project(self, records):
        """Filtra registros por empleados con tareas en proyectos."""
        Task = self.env['project.task']
        employee_ids_with_tasks = set()
        for task in Task.search([('project_id', '!=', False)]):
            for user in task.user_ids:
                emp = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
                if emp:
                    employee_ids_with_tasks.add(emp.id)
        if not employee_ids_with_tasks:
            return records.browse()
        return records.filtered(lambda r: r.employee_id.id in employee_ids_with_tasks)

    def _get_excel_headers(self):
        return [
            _('Empleado'),
            _('Departamento'),
            _('Puesto'),
            _('Fecha ingreso'),
            _('Antigüedad (años)'),
            _('Período inicio'),
            _('Período fin'),
            _('Días asignados'),
            _('Días gozados'),
            _('Saldo'),
            _('Constancias'),
            _('Pagos'),
            _('Estado'),
        ]

    def _get_allocation_state_label(self, state):
        labels = {
            'draft': _('Borrador'),
            'confirm': _('Por aprobar'),
            'validate': _('Aprobada'),
            'refuse': _('Rechazada'),
        }
        return labels.get(state, state or '')

    def _generate_excel_content(self, records):
        """Genera el contenido del archivo Excel."""
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        header_fmt = workbook.add_format({'bold': True, 'border': 1})
        cell_fmt = workbook.add_format({'border': 1})
        date_fmt = workbook.add_format({'border': 1, 'num_format': 'dd/mm/yyyy'})
        headers = self._get_excel_headers()
        if self.report_type == 'department':
            self._write_excel_by_department(workbook, records, headers, header_fmt, cell_fmt, date_fmt)
        elif self.report_type == 'project' and self._project_available():
            self._write_excel_by_project(workbook, records, headers, header_fmt, cell_fmt, date_fmt)
        else:
            self._write_excel_flat(workbook, records, headers, header_fmt, cell_fmt, date_fmt)
        workbook.close()
        output.seek(0)
        return output.read()

    def _write_excel_flat(self, workbook, records, headers, header_fmt, cell_fmt, date_fmt):
        sheet = workbook.add_worksheet(_('Estatus Vacaciones'))
        for col, h in enumerate(headers):
            sheet.write(0, col, h, header_fmt)
        sheet.set_column(0, 0, 25)
        sheet.set_column(1, 1, 20)
        for row, rec in enumerate(records, start=1):
            sheet.write(row, 0, rec.employee_name or '', cell_fmt)
            sheet.write(row, 1, rec.department_id.name if rec.department_id else '', cell_fmt)
            sheet.write(row, 2, rec.job_id.name if rec.job_id else '', cell_fmt)
            sheet.write(row, 3, rec.contract_date_start or '', date_fmt if rec.contract_date_start else cell_fmt)
            sheet.write(row, 4, rec.seniority_years or 0, cell_fmt)
            sheet.write(row, 5, rec.period_start or '', date_fmt if rec.period_start else cell_fmt)
            sheet.write(row, 6, rec.period_end or '', date_fmt if rec.period_end else cell_fmt)
            sheet.write(row, 7, rec.days_entitled or 0, cell_fmt)
            sheet.write(row, 8, rec.days_taken or 0, cell_fmt)
            sheet.write(row, 9, rec.days_remaining or 0, cell_fmt)
            sheet.write(row, 10, rec.constancia_count or 0, cell_fmt)
            sheet.write(row, 11, rec.paid_count or 0, cell_fmt)
            sheet.write(row, 12, self._get_allocation_state_label(rec.allocation_state), cell_fmt)

    def _write_excel_by_department(self, workbook, records, headers, header_fmt, cell_fmt, date_fmt):
        sheet = workbook.add_worksheet(_('Estatus Vacaciones'))
        row = 0
        departments = records.mapped('department_id')
        dept_list = sorted(
            [d for d in departments if d],
            key=lambda d: (d.name or ''),
        )
        if any(not r.department_id for r in records):
            dept_list.append(False)
        for dept in dept_list:
            dept_records = records.filtered(lambda r, d=dept: r.department_id == d)
            sheet.write(row, 0, dept.name if dept else _('Sin departamento'), header_fmt)
            sheet.merge_range(row, 0, row, len(headers) - 1, dept.name if dept else _('Sin departamento'), header_fmt)
            row += 1
            for col, h in enumerate(headers):
                sheet.write(row, col, h, header_fmt)
            row += 1
            for rec in dept_records:
                sheet.write(row, 0, rec.employee_name or '', cell_fmt)
                sheet.write(row, 1, rec.department_id.name if rec.department_id else '', cell_fmt)
                sheet.write(row, 2, rec.job_id.name if rec.job_id else '', cell_fmt)
                sheet.write(row, 3, rec.contract_date_start or '', date_fmt if rec.contract_date_start else cell_fmt)
                sheet.write(row, 4, rec.seniority_years or 0, cell_fmt)
                sheet.write(row, 5, rec.period_start or '', date_fmt if rec.period_start else cell_fmt)
                sheet.write(row, 6, rec.period_end or '', date_fmt if rec.period_end else cell_fmt)
                sheet.write(row, 7, rec.days_entitled or 0, cell_fmt)
                sheet.write(row, 8, rec.days_taken or 0, cell_fmt)
                sheet.write(row, 9, rec.days_remaining or 0, cell_fmt)
                sheet.write(row, 10, rec.constancia_count or 0, cell_fmt)
                sheet.write(row, 11, rec.paid_count or 0, cell_fmt)
                sheet.write(row, 12, self._get_allocation_state_label(rec.allocation_state), cell_fmt)
                row += 1
            row += 1

    def _write_excel_by_project(self, workbook, records, headers, header_fmt, cell_fmt, date_fmt):
        Project = self.env['project.project']
        emp_to_projects = {}
        for rec in records:
            emp = rec.employee_id
            if emp.user_id:
                tasks = self.env['project.task'].search([
                    ('user_ids', 'in', emp.user_id.ids),
                    ('project_id', '!=', False),
                ])
                for t in tasks:
                    if t.project_id:
                        key = emp.id
                        if key not in emp_to_projects:
                            emp_to_projects[key] = set()
                        emp_to_projects[key].add(t.project_id.id)
        sheet = workbook.add_worksheet(_('Estatus Vacaciones'))
        row = 0
        project_ids_seen = set()
        for proj in Project.search([('id', 'in', list(set(pid for pids in emp_to_projects.values() for pid in pids)))]):
            emp_ids = [eid for eid, pids in emp_to_projects.items() if proj.id in pids]
            proj_records = records.filtered(lambda r: r.employee_id.id in emp_ids)
            if not proj_records:
                continue
            sheet.write(row, 0, proj.name, header_fmt)
            sheet.merge_range(row, 0, row, len(headers) - 1, proj.name, header_fmt)
            row += 1
            for col, h in enumerate(headers):
                sheet.write(row, col, h, header_fmt)
            row += 1
            for rec in proj_records:
                sheet.write(row, 0, rec.employee_name or '', cell_fmt)
                sheet.write(row, 1, rec.department_id.name if rec.department_id else '', cell_fmt)
                sheet.write(row, 2, rec.job_id.name if rec.job_id else '', cell_fmt)
                sheet.write(row, 3, rec.contract_date_start or '', date_fmt if rec.contract_date_start else cell_fmt)
                sheet.write(row, 4, rec.seniority_years or 0, cell_fmt)
                sheet.write(row, 5, rec.period_start or '', date_fmt if rec.period_start else cell_fmt)
                sheet.write(row, 6, rec.period_end or '', date_fmt if rec.period_end else cell_fmt)
                sheet.write(row, 7, rec.days_entitled or 0, cell_fmt)
                sheet.write(row, 8, rec.days_taken or 0, cell_fmt)
                sheet.write(row, 9, rec.days_remaining or 0, cell_fmt)
                sheet.write(row, 10, rec.constancia_count or 0, cell_fmt)
                sheet.write(row, 11, rec.paid_count or 0, cell_fmt)
                sheet.write(row, 12, self._get_allocation_state_label(rec.allocation_state), cell_fmt)
                row += 1
            row += 1

    def action_generate_excel(self):
        """Genera el archivo Excel y retorna descarga."""
        self.ensure_one()
        if self.report_type == 'project' and not self._project_available():
            raise UserError(_('Para usar "Por Proyecto/Asignación" debe instalar el módulo project.'))
        if not xlsxwriter:
            raise UserError(_('La biblioteca xlsxwriter no está instalada. Contacte al administrador.'))
        records = self._get_filtered_records()
        if not records:
            raise UserError(_('No hay datos que coincidan con los filtros seleccionados.'))
        content = self._generate_excel_content(records)
        filename = f'Estatus_Vacaciones_{date.today().strftime("%Y%m%d")}.xlsx'
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': base64.b64encode(content),
            'type': 'binary',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true&filename={filename}',
            'target': 'self',
        }

    def action_show_onscreen(self):
        """Abre la vista del libro con el domain aplicado."""
        self.ensure_one()
        if self.report_type == 'project' and not self._project_available():
            raise UserError(_('Para usar "Por Proyecto/Asignación" debe instalar el módulo project.'))
        records = self._get_filtered_records()
        domain = [('id', 'in', records.ids)] if records else [('id', 'in', [])]
        action = self.env.ref('l10n_hn_hr_payroll.action_gn_hn_vacation_libro').read()[0]
        action['domain'] = domain
        action['context'] = {'search_default_approved': 1}
        return action
