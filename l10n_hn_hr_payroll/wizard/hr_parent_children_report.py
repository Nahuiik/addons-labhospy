# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

import base64
import io
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrParentChildrenReportWizard(models.TransientModel):
    _name = 'hr.parent.children.report.wizard'
    _description = 'Reporte de Padres, Madres e Hijos'

    company_id = fields.Many2one(
        'res.company', string='Compañía',
        default=lambda self: self.env.company, required=True)
    department_ids = fields.Many2many(
        'hr.department', string='Departamentos',
        help='Dejar vacío para incluir todos los departamentos.')

    _CHILD_RELATIONS = ('Hijo', 'Hija', 'Hijastro', 'Hijastra')

    def _get_employees(self):
        domain = [
            ('company_id', '=', self.company_id.id),
            ('active', '=', True),
        ]
        if self.department_ids:
            domain.append(('department_id', 'in', self.department_ids.ids))
        return self.env['hr.employee'].search(domain, order='name')

    def _get_children(self, employees, max_age):
        """Retorna registros hr.employee.family que son hijos con edad < max_age."""
        today = date.today()
        result = []
        for emp in employees:
            for fam in emp.family_ids:
                if not fam.relation_id or fam.relation_id.name not in self._CHILD_RELATIONS:
                    continue
                if not fam.birthdate:
                    continue
                from dateutil.relativedelta import relativedelta
                age = relativedelta(today, fam.birthdate).years
                if age < max_age:
                    result.append((fam, emp, age))
        result.sort(key=lambda x: x[1].name)
        return result

    def _build_parent_warnings(self, emp):
        warnings = []
        if emp.parent_type == 'father' and emp.sex == 'female':
            warnings.append(_('Mujer marcada como padre'))
        elif emp.parent_type == 'mother' and emp.sex == 'male':
            warnings.append(_('Hombre marcado como madre'))
        has_children = any(
            f.relation_id and f.relation_id.name in self._CHILD_RELATIONS
            for f in emp.family_ids
        )
        if not has_children:
            warnings.append(_('Sin hijos registrados'))
        return '; '.join(warnings)

    def action_export_excel(self):
        self.ensure_one()
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
            from openpyxl.utils import get_column_letter
        except ImportError:
            raise UserError(_('Se requiere openpyxl. Instale: pip install openpyxl'))

        employees = self._get_employees()
        if not employees:
            raise UserError(_('No se encontraron empleados activos con los filtros seleccionados.'))

        wb = Workbook()
        wb.remove(wb.active)

        header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
        header_font = Font(bold=True, color='FFFFFF')
        warn_font = Font(color='FF0000')
        border = Border(
            left=Side(style='thin', color='A5A5A5'),
            right=Side(style='thin', color='A5A5A5'),
            top=Side(style='thin', color='A5A5A5'),
            bottom=Side(style='thin', color='A5A5A5'),
        )
        center = Alignment(horizontal='center', vertical='center')

        def _write_header(ws, headers):
            for col, h in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=h)
                cell.fill = header_fill
                cell.font = header_font
                cell.border = border
                cell.alignment = center

        def _set_col_widths(ws, widths):
            for col, w in enumerate(widths, 1):
                ws.column_dimensions[get_column_letter(col)].width = w

        # ── Hoja 1: Padres ─────────────────────────────────────────
        fathers = employees.filtered(lambda e: e.parent_type == 'father')
        ws_fathers = wb.create_sheet('Padres')
        father_headers = ['Nombre', 'DNI', 'Puesto', 'Departamento', 'Observaciones']
        _write_header(ws_fathers, father_headers)
        for row, emp in enumerate(fathers.sorted(key=lambda e: e.name), 2):
            obs = self._build_parent_warnings(emp)
            vals = [
                emp.name or '',
                emp.identification_id or '',
                emp.job_id.name if emp.job_id else '',
                emp.department_id.name if emp.department_id else '',
                obs,
            ]
            for col, val in enumerate(vals, 1):
                cell = ws_fathers.cell(row=row, column=col, value=val)
                cell.border = border
                if col == 5 and val:
                    cell.font = warn_font
        _set_col_widths(ws_fathers, [30, 18, 25, 25, 40])

        # ── Hoja 2: Madres ─────────────────────────────────────────
        mothers = employees.filtered(lambda e: e.parent_type == 'mother')
        ws_mothers = wb.create_sheet('Madres')
        mother_headers = ['Nombre', 'DNI', 'Puesto', 'Departamento', 'Observaciones']
        _write_header(ws_mothers, mother_headers)
        for row, emp in enumerate(mothers.sorted(key=lambda e: e.name), 2):
            obs = self._build_parent_warnings(emp)
            vals = [
                emp.name or '',
                emp.identification_id or '',
                emp.job_id.name if emp.job_id else '',
                emp.department_id.name if emp.department_id else '',
                obs,
            ]
            for col, val in enumerate(vals, 1):
                cell = ws_mothers.cell(row=row, column=col, value=val)
                cell.border = border
                if col == 5 and val:
                    cell.font = warn_font
        _set_col_widths(ws_mothers, [30, 18, 25, 25, 40])

        # ── Hoja 3: Hijos menores de 18 ───────────────────────────
        children_18 = self._get_children(employees, 18)
        ws_18 = wb.create_sheet('Hijos menores de 18')
        child_headers = [
            'Nombre del Hijo', 'Fecha Nacimiento', 'Edad',
            'Parentesco', 'Nombre del Empleado', 'DNI Empleado',
            'Puesto', 'Departamento',
        ]
        _write_header(ws_18, child_headers)
        for row, (fam, emp, age) in enumerate(children_18, 2):
            vals = [
                fam.name or '',
                fam.birthdate.strftime('%d/%m/%Y') if fam.birthdate else '',
                age,
                fam.relation_id.name if fam.relation_id else '',
                emp.name or '',
                emp.identification_id or '',
                emp.job_id.name if emp.job_id else '',
                emp.department_id.name if emp.department_id else '',
            ]
            for col, val in enumerate(vals, 1):
                cell = ws_18.cell(row=row, column=col, value=val)
                cell.border = border
        _set_col_widths(ws_18, [28, 16, 8, 14, 28, 18, 25, 25])

        # ── Hoja 4: Hijos menores de 12 ───────────────────────────
        children_12 = self._get_children(employees, 12)
        ws_12 = wb.create_sheet('Hijos menores de 12')
        _write_header(ws_12, child_headers)
        for row, (fam, emp, age) in enumerate(children_12, 2):
            vals = [
                fam.name or '',
                fam.birthdate.strftime('%d/%m/%Y') if fam.birthdate else '',
                age,
                fam.relation_id.name if fam.relation_id else '',
                emp.name or '',
                emp.identification_id or '',
                emp.job_id.name if emp.job_id else '',
                emp.department_id.name if emp.department_id else '',
            ]
            for col, val in enumerate(vals, 1):
                cell = ws_12.cell(row=row, column=col, value=val)
                cell.border = border
        _set_col_widths(ws_12, [28, 16, 8, 14, 28, 18, 25, 25])

        # ── Hoja 5: Resumen por departamento ──────────────────────
        ws_resumen = wb.create_sheet('Resumen por Departamento')
        resumen_headers = ['Departamento', 'Padres', 'Madres', 'Hijos < 18', 'Hijos < 12']
        _write_header(ws_resumen, resumen_headers)

        dept_stats = {}
        for emp in fathers:
            dept = emp.department_id.name if emp.department_id else _('Sin departamento')
            dept_stats.setdefault(dept, [0, 0, 0, 0])
            dept_stats[dept][0] += 1
        for emp in mothers:
            dept = emp.department_id.name if emp.department_id else _('Sin departamento')
            dept_stats.setdefault(dept, [0, 0, 0, 0])
            dept_stats[dept][1] += 1
        for _fam, emp, _age in children_18:
            dept = emp.department_id.name if emp.department_id else _('Sin departamento')
            dept_stats.setdefault(dept, [0, 0, 0, 0])
            dept_stats[dept][2] += 1
        for _fam, emp, _age in children_12:
            dept = emp.department_id.name if emp.department_id else _('Sin departamento')
            dept_stats.setdefault(dept, [0, 0, 0, 0])
            dept_stats[dept][3] += 1

        bold_font = Font(bold=True)
        totals = [0, 0, 0, 0]
        for row, (dept, counts) in enumerate(sorted(dept_stats.items()), 2):
            ws_resumen.cell(row=row, column=1, value=dept).border = border
            for col, val in enumerate(counts, 2):
                cell = ws_resumen.cell(row=row, column=col, value=val)
                cell.border = border
                cell.alignment = center
                totals[col - 2] += val

        total_row = len(dept_stats) + 2
        cell = ws_resumen.cell(row=total_row, column=1, value=_('TOTAL'))
        cell.font = bold_font
        cell.border = border
        for col, val in enumerate(totals, 2):
            cell = ws_resumen.cell(row=total_row, column=col, value=val)
            cell.font = bold_font
            cell.border = border
            cell.alignment = center
        _set_col_widths(ws_resumen, [30, 12, 12, 14, 14])

        # ── Descargar ──────────────────────────────────────────────
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        filename = 'Reporte_Padres_Madres_Hijos.xlsx'
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(buffer.read()),
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%d?download=true' % attachment.id,
            'target': 'self',
        }
