# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

import base64
import io
import re
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    Workbook = None


class HrRecurringConceptReport(models.TransientModel):
    """Wizard para exportar reporte de conceptos recurrentes a Excel"""
    _name = 'hr.employee.recurring.concept.report'
    _description = 'Reporte de Conceptos Recurrentes'

    employee_ids = fields.Many2many(
        'hr.employee',
        string='Empleados',
        help='Dejar vacío para incluir todos los empleados'
    )
    concept_type = fields.Selection([
        ('all', 'Todos'),
        ('income', 'Ingresos'),
        ('deduction', 'Deducciones'),
    ], string='Tipo de Concepto', required=True, default='all')
    active_filter = fields.Selection([
        ('all', 'Todos'),
        ('active_only', 'Solo Activos'),
        ('inactive_only', 'Solo Inactivos'),
    ], string='Estado', required=True, default='active_only')
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        required=True,
        default=lambda self: self.env.company
    )

    def _get_domain(self):
        """Construir dominio para buscar conceptos"""
        domain = [('company_id', '=', self.company_id.id)]
        if self.employee_ids:
            domain.extend([
                '|',
                ('employee_id', '=', False),
                ('employee_id', 'in', self.employee_ids.ids),
            ])
        else:
            domain.extend([
                '|',
                ('employee_id', '=', False),
                ('employee_id.company_id', '=', self.company_id.id),
            ])
        if self.concept_type != 'all':
            domain.append(('concept_type', '=', self.concept_type))
        if self.active_filter == 'active_only':
            domain.append(('active', '=', True))
        elif self.active_filter == 'inactive_only':
            domain.append(('active', '=', False))
        return domain

    def _get_concepts(self):
        domain = self._get_domain()
        return self.env['hr.employee.recurring.concept'].search(domain, order='employee_id, name')

    def action_export_excel(self):
        """Generar reporte Excel de conceptos recurrentes"""
        self.ensure_one()
        if not Workbook:
            raise UserError(_('Se requiere openpyxl. Instale: pip install openpyxl'))

        concepts = self._get_concepts()
        if not concepts:
            raise UserError(_('No hay conceptos recurrentes que coincidan con los filtros.'))

        wb = Workbook()
        wb.remove(wb.active)

        gray_border = Border(
            left=Side(style='thin', color='A5A5A5'),
            right=Side(style='thin', color='A5A5A5'),
            top=Side(style='thin', color='A5A5A5'),
            bottom=Side(style='thin', color='A5A5A5'),
        )
        currency = self.company_id.currency_id or self.env.company.currency_id
        symbol = (currency.symbol or '').replace('"', '""')
        currency_fmt = '"%s"#,##0.00' % symbol if symbol else '#,##0.00'
        header_fill = PatternFill(start_color='A52A2A', end_color='A52A2A', fill_type='solid')
        header_font = Font(bold=True, color='FFFFFF')
        subtotal_fill = PatternFill(start_color='808080', end_color='808080', fill_type='solid')
        subtotal_font = Font(bold=True, color='FFFFFF')

        def _style_cell(cell, fill=None, font=None, border=None, number_format=None):
            if fill:
                cell.fill = fill
            if font:
                cell.font = font
            if border:
                cell.border = border
            if number_format:
                cell.number_format = number_format

        def _sanitize_sheet_name(name):
            if not name:
                return _('Sin nombre')
            name = str(name)
            for c in ':\\/?*[]':
                name = name.replace(c, '_')
            return (name[:31] if len(name) > 31 else name) or _('Sin nombre')

        CONCEPT_TYPE_LABELS = {'income': _('Ingreso'), 'deduction': _('Deducción')}
        AMOUNT_TYPE_LABELS = {'fixed': _('Fijo'), 'percentage': _('Porcentaje')}
        APPLY_BIWEEK_LABELS = {'both': _('Ambas'), 'first': _('1ra'), 'second': _('2da')}

        # --- Hoja Detalle ---
        ws_detalle = wb.create_sheet(_sanitize_sheet_name(_('Detalle')), 0)
        detalle_headers = [
            _('Empleado'), _('Código'), _('Nombre'), _('Tipo'), _('Tipo Monto'), _('Monto'),
            _('Fecha Inicio'), _('Fecha Fin'), _('Aplicar Quincena'), _('Es Préstamo'),
            _('Total'), _('Cuotas'), _('Pagadas'), _('Restante'), _('Activo'),
            _('Departamento'), _('Proyecto'), _('Asignación'),
        ]
        currency_cols_detalle = (6, 10, 14)  # Monto, Total, Restante
        for c, h in enumerate(detalle_headers, 1):
            cell = ws_detalle.cell(row=1, column=c, value=h)
            _style_cell(cell, fill=header_fill, font=header_font, border=gray_border)

        for row, rec in enumerate(concepts, 2):
            emp = rec.employee_id
            emp_name = emp.name if emp else _('Compartido')
            dept = emp.department_id.name if emp and emp.department_id else ''
            proj = emp.project_id.name if emp and emp.project_id else ''
            asig = emp.assignment_id.name if emp and emp.assignment_id else ''
            vals = [
                emp_name, rec.code or '', rec.name, CONCEPT_TYPE_LABELS.get(rec.concept_type, rec.concept_type),
                AMOUNT_TYPE_LABELS.get(rec.amount_type, rec.amount_type), rec.amount,
                rec.date_start.strftime('%Y-%m-%d') if rec.date_start else '',
                rec.date_end.strftime('%Y-%m-%d') if rec.date_end else '',
                APPLY_BIWEEK_LABELS.get(rec.apply_biweek, rec.apply_biweek or ''),
                _('Sí') if rec.is_loan else _('No'),
                rec.total_amount if rec.is_loan else 0.0, rec.installments, rec.paid_installments,
                rec.remaining_amount if rec.is_loan else 0.0, _('Sí') if rec.active else _('No'),
                dept, proj, asig,
            ]
            for c, val in enumerate(vals, 1):
                cell = ws_detalle.cell(row=row, column=c, value=val)
                cell.border = gray_border
                if c in currency_cols_detalle and isinstance(val, (int, float)):
                    cell.number_format = currency_fmt

        for c in range(1, len(detalle_headers) + 1):
            ws_detalle.column_dimensions[get_column_letter(c)].width = 14

        # --- Hoja Resumen por Empleado ---
        ws_emp = wb.create_sheet(_sanitize_sheet_name(_('Resumen por Empleado')), 1)
        emp_headers = [_('Empleado'), _('# Conceptos'), _('Total Ingresos'), _('Total Deducciones'), _('Total Restante Préstamos')]
        for c, h in enumerate(emp_headers, 1):
            cell = ws_emp.cell(row=1, column=c, value=h)
            _style_cell(cell, fill=header_fill, font=header_font, border=gray_border)

        by_emp = {}
        for rec in concepts:
            key = rec.employee_id.id if rec.employee_id else 0
            if key not in by_emp:
                by_emp[key] = {'concepts': [], 'emp': rec.employee_id}
            by_emp[key]['concepts'].append(rec)

        emp_row = 2
        for emp_id in sorted(by_emp.keys(), key=lambda x: (by_emp[x]['emp'].name if by_emp[x]['emp'] else 'ZZZ')):
            data = by_emp[emp_id]
            emp = data['emp']
            emps_concepts = data['concepts']
            emp_name = emp.name if emp else _('Compartido')
            tot_ing = sum(c.amount for c in emps_concepts if c.concept_type == 'income')
            tot_ded = sum(c.amount for c in emps_concepts if c.concept_type == 'deduction')
            tot_rest = sum(c.remaining_amount for c in emps_concepts if c.is_loan)
            for c, val in enumerate([emp_name, len(emps_concepts), tot_ing, tot_ded, tot_rest], 1):
                cell = ws_emp.cell(row=emp_row, column=c, value=val)
                cell.border = gray_border
                if c >= 3:
                    cell.number_format = currency_fmt
            emp_row += 1

        total_row = emp_row
        for col in range(1, 6):
            cell = ws_emp.cell(row=total_row, column=col)
            _style_cell(cell, fill=subtotal_fill, font=subtotal_font, border=gray_border)
            if col == 1:
                cell.value = _('TOTAL')
            else:
                idx = col - 1
                cell.value = sum(
                    len(by_emp[k]['concepts']) if idx == 0 else
                    sum(conc.amount for conc in by_emp[k]['concepts'] if conc.concept_type == 'income') if idx == 1 else
                    sum(conc.amount for conc in by_emp[k]['concepts'] if conc.concept_type == 'deduction') if idx == 2 else
                    sum(conc.remaining_amount for conc in by_emp[k]['concepts'] if conc.is_loan)
                    for k in by_emp
                )
                if col >= 3:
                    cell.number_format = currency_fmt
        for c in range(1, 6):
            ws_emp.column_dimensions[get_column_letter(c)].width = 18

        # --- Hoja Resumen por Tipo ---
        ws_tipo = wb.create_sheet(_sanitize_sheet_name(_('Resumen por Tipo')), 2)
        tipo_headers = [_('Tipo'), _('# Conceptos'), _('Total Monto')]
        for c, h in enumerate(tipo_headers, 1):
            cell = ws_tipo.cell(row=1, column=c, value=h)
            _style_cell(cell, fill=header_fill, font=header_font, border=gray_border)

        by_tipo = {'income': [], 'deduction': []}
        for rec in concepts:
            by_tipo[rec.concept_type].append(rec)

        tipo_row = 2
        for t in ['income', 'deduction']:
            items = by_tipo[t]
            tot = sum(c.amount for c in items)
            for c, val in enumerate([CONCEPT_TYPE_LABELS[t], len(items), tot], 1):
                cell = ws_tipo.cell(row=tipo_row, column=c, value=val)
                cell.border = gray_border
                if c == 3:
                    cell.number_format = currency_fmt
            tipo_row += 1

        total_row = tipo_row
        for c in range(1, 4):
            cell = ws_tipo.cell(row=total_row, column=c)
            _style_cell(cell, fill=subtotal_fill, font=subtotal_font, border=gray_border)
            if c == 1:
                cell.value = _('TOTAL')
            elif c == 2:
                cell.value = len(concepts)
            else:
                cell.value = sum(c.amount for c in concepts)
                cell.number_format = currency_fmt
        for c in range(1, 4):
            ws_tipo.column_dimensions[get_column_letter(c)].width = 18

        # --- Hoja Resumen por Departamento ---
        ws_dept = wb.create_sheet(_sanitize_sheet_name(_('Resumen por Departamento')), 3)
        dept_headers = [_('Departamento'), _('# Conceptos'), _('Total Ingresos'), _('Total Deducciones')]
        for c, h in enumerate(dept_headers, 1):
            cell = ws_dept.cell(row=1, column=c, value=h)
            _style_cell(cell, fill=header_fill, font=header_font, border=gray_border)

        by_dept = {}
        for rec in concepts:
            emp = rec.employee_id
            dept_name = (emp.department_id.name if emp and emp.department_id else _('Sin departamento'))
            if dept_name not in by_dept:
                by_dept[dept_name] = []
            by_dept[dept_name].append(rec)

        dept_row = 2
        for dept_name in sorted(by_dept.keys()):
            items = by_dept[dept_name]
            tot_ing = sum(c.amount for c in items if c.concept_type == 'income')
            tot_ded = sum(c.amount for c in items if c.concept_type == 'deduction')
            for c, val in enumerate([dept_name, len(items), tot_ing, tot_ded], 1):
                cell = ws_dept.cell(row=dept_row, column=c, value=val)
                cell.border = gray_border
                if c >= 3:
                    cell.number_format = currency_fmt
            dept_row += 1

        total_row = dept_row
        for c in range(1, 5):
            cell = ws_dept.cell(row=total_row, column=c)
            _style_cell(cell, fill=subtotal_fill, font=subtotal_font, border=gray_border)
            if c == 1:
                cell.value = _('TOTAL')
            elif c == 2:
                cell.value = len(concepts)
            else:
                cell.value = sum(c.amount for c in concepts if c.concept_type == ('income' if c == 3 else 'deduction'))
                cell.number_format = currency_fmt
        for c in range(1, 5):
            ws_dept.column_dimensions[get_column_letter(c)].width = 18

        # Descargar
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        safe_name = re.sub(r'[^\w\s\-]', '', _('Conceptos_Recurrentes'))
        filename = '%s_%s.xlsx' % (safe_name.replace(' ', '_'), datetime.now().strftime('%Y%m%d_%H%M%S'))
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
