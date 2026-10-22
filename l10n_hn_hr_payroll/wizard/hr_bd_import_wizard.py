# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

"""
Wizard para importación masiva de Beneficios y Deducciones (BD).
Modelo destino: l10n.hn.payroll.line.bd dentro de la planilla.
"""

import base64
import io
import re
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError

try:
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


# Índices de columnas en la plantilla (0-based)
COL_EMPLOYEE_ID = 0
COL_IDENTIDAD = 1
COL_NOMBRE = 2
COL_COMPANIA = 3
COL_DEPARTAMENTO = 4
COL_PERIODO = 5
COL_CODIGO_CONCEPTO = 6
COL_MONTO = 7
COL_OBSERVACIONES = 8

HEADERS = [
    'employee_id',
    'Identidad',
    'Nombre Colaborador',
    'Compañía',
    'Departamento',
    'Periodo',
    'Código Concepto',
    'Monto',
    'Observaciones',
]


class HrBdImportWizard(models.TransientModel):
    _name = 'hr.bd.import.wizard'
    _description = 'Importar Beneficios y Deducciones'

    payroll_sheet_id = fields.Many2one(
        'l10n.hn.payroll.sheet', string='Planilla',
        help='Si se abre desde una planilla, se pre-llena. Si no, se crea/usa una según período.',
        ondelete='set null',
    )
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company,
    )
    payroll_period_id = fields.Many2one(
        'l10n.hn.payroll.period', string='Período',
        domain="[('company_id', '=', company_id)]",
        help='Período de nómina (quincena) para la importación.',
    )
    department_id = fields.Many2one(
        'hr.department', string='Departamento',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help='Opcional: filtrar empleados por departamento en la plantilla.',
    )
    employee_ids = fields.Many2many(
        'hr.employee', string='Empleados',
        domain="[('active', '=', True), ('company_id', '=', company_id)]",
        help='Opcional: limitar plantilla a estos empleados.',
    )
    file_data = fields.Binary(string='Archivo Excel', attachment=False)
    file_name = fields.Char(string='Nombre archivo')
    skip_empty = fields.Boolean(
        string='Omitir filas con monto cero',
        default=True,
        help='Si está activo, se omiten filas con monto 0 o vacío y filas sin código de concepto cuando el monto es 0 o está vacío.',
    )
    result_summary = fields.Text(string='Resumen', readonly=True)
    result_log = fields.Binary(string='Log de importación', readonly=True, attachment=False)
    result_log_filename = fields.Char(string='Nombre log', readonly=True)
    state = fields.Selection([
        ('draft', 'Configuración'),
        ('done', 'Completado'),
    ], default='draft', required=True)

    @api.onchange('payroll_sheet_id')
    def _onchange_payroll_sheet_id(self):
        if self.payroll_sheet_id:
            self.company_id = self.payroll_sheet_id.company_id
            self.payroll_period_id = self.payroll_sheet_id.payroll_period_id
            self.department_id = self.payroll_sheet_id.department_id

    def _concept_domain_base(self):
        return [
            ('for_payroll', '=', True),
            ('employee_id', '=', False),
            ('active', '=', True),
            '|',
            ('company_id', '=', False),
            ('company_id', '=', self.company_id.id),
        ]

    def _get_employees_for_template(self):
        """Empleados a incluir en la plantilla según filtros."""
        domain = [
            ('active', '=', True),
            ('company_id', '=', self.company_id.id),
        ]
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        if self.employee_ids:
            domain.append(('id', 'in', self.employee_ids.ids))
        employees = self.env['hr.employee'].search(domain, order='name')
        if not employees:
            raise UserError(_('No hay empleados que coincidan con los filtros.'))
        period = self.payroll_period_id or (
            self.payroll_sheet_id.payroll_period_id if self.payroll_sheet_id else None
        )
        if period and period.date_start and period.date_end:
            versions = self.env['hr.version'].search([
                ('employee_id', 'in', employees.ids),
                ('contract_date_start', '<=', period.date_end),
                '|', ('contract_date_end', '=', False),
                ('contract_date_end', '>=', period.date_start),
            ])
            emp_ids = versions.mapped('employee_id').ids
            employees = employees.filtered(lambda e: e.id in emp_ids)
        return employees

    def action_download_template(self):
        """Generar y descargar plantilla Excel."""
        if not OPENPYXL_AVAILABLE:
            raise UserError(_('Se requiere openpyxl. Instale: pip install openpyxl'))
        period = self.payroll_period_id or (
            self.payroll_sheet_id.payroll_period_id if self.payroll_sheet_id else None
        )
        if not period:
            raise UserError(_('Seleccione el período o una planilla antes de descargar la plantilla.'))
        employees = self._get_employees_for_template()
        wb = self._build_template_workbook(employees)
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        period_name = self.payroll_period_id.name or 'plantilla'
        filename = f'Importacion_BD_{period_name.replace(" ", "_")}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def _build_template_workbook(self, employees):
        """Construir workbook con formato, freeze panes, autofilter."""
        wb = Workbook()
        ws = wb.active
        ws.title = 'Importación'
        header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
        header_font = Font(bold=True, color='FFFFFF')
        editable_fill = PatternFill(start_color='E8F4EA', end_color='E8F4EA', fill_type='solid')
        readonly_fill = PatternFill(start_color='F5F5F5', end_color='F5F5F5', fill_type='solid')
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin'),
        )
        for c, h in enumerate(HEADERS, 1):
            cell = ws.cell(row=1, column=c, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.border = thin_border
            cell.alignment = Alignment(horizontal='center', wrap_text=True)
        period = self.payroll_period_id or (
            self.payroll_sheet_id.payroll_period_id if self.payroll_sheet_id else None
        )
        period_str = f'{period.date_start} - {period.date_end}' if period and period.date_start else ''
        for r, emp in enumerate(employees, 2):
            row_data = [
                emp.id,
                emp.identification_id or '',
                emp.name or '',
                emp.company_id.name or '',
                emp.department_id.name or '',
                period_str,
                '',  # Código Concepto - editable
                0.0,  # Monto - editable
                '',
            ]
            for c, val in enumerate(row_data, 1):
                cell = ws.cell(row=r, column=c, value=val)
                cell.border = thin_border
                if c in (7, 8):  # Código Concepto, Monto
                    cell.fill = editable_fill
                    if c == 8:
                        cell.number_format = '0.00'
                else:
                    cell.fill = readonly_fill
        ws.freeze_panes = 'A2'
        if employees:
            ws.auto_filter.ref = ws.dimensions
        widths = [12, 15, 30, 20, 20, 22, 18, 12, 25]
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws_cat = wb.create_sheet('Catálogos')
        ws_cat['A1'] = _('Conceptos disponibles (for_payroll=True)')
        ws_cat['A1'].font = Font(bold=True)
        concepts = self.env['hr.employee.recurring.concept'].search(
            self._concept_domain_base(),
            order='code',
        )
        for r, conc in enumerate(concepts, 2):
            ws_cat.cell(row=r, column=1, value=conc.code or '')
            ws_cat.cell(row=r, column=2, value=conc.name or '')
        ws_cat.column_dimensions['A'].width = 20
        ws_cat.column_dimensions['B'].width = 35
        ws_help = wb.create_sheet(_('Instrucciones'))
        instr = [
            _('Varios conceptos para el mismo empleado:'),
            _('• Duplique la fila (mismo employee_id y/o identidad); copie nombre y datos de cabecera.'),
            _('• En cada fila use un Código Concepto distinto con su Monto.'),
            _('• La importación crea una línea en Beneficios y deducciones por cada fila válida.'),
        ]
        for i, line in enumerate(instr, 1):
            ws_help.cell(row=i, column=1, value=line)
        ws_help.column_dimensions['A'].width = 85
        return wb

    def _get_or_create_sheet(self):
        """Obtener o crear planilla en borrador para el período."""
        if self.payroll_sheet_id:
            if self.payroll_sheet_id.state != 'draft':
                raise UserError(_('La planilla debe estar en borrador para importar.'))
            return self.payroll_sheet_id
        if not self.payroll_period_id:
            raise UserError(_('Seleccione el período o una planilla.'))
        sheet = self.env['l10n.hn.payroll.sheet'].search([
            ('payroll_period_id', '=', self.payroll_period_id.id),
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'draft'),
        ], limit=1)
        if not sheet:
            sheet = self.env['l10n.hn.payroll.sheet'].create({
                'payroll_period_id': self.payroll_period_id.id,
                'company_id': self.company_id.id,
            })
        return sheet

    def _resolve_employee(self, row_data, row_num):
        """Resolver empleado desde fila. Prioridad: employee_id, luego Identidad."""
        emp_id_val = row_data.get(COL_EMPLOYEE_ID)
        identidad_val = str(row_data.get(COL_IDENTIDAD) or '').strip()
        if emp_id_val is not None and emp_id_val != '':
            try:
                eid = int(float(emp_id_val))
                emp = self.env['hr.employee'].browse(eid)
                if emp.exists():
                    return emp
            except (ValueError, TypeError):
                pass
        if identidad_val:
            identidad_clean = re.sub(r'[^0-9]', '', identidad_val)
            emp = self.env['hr.employee'].search([
                ('company_id', '=', self.company_id.id),
                '|', ('identification_id', '=', identidad_val),
                ('identification_id', '=', identidad_clean),
            ], limit=1)
            if emp:
                return emp
        return None

    def _resolve_concept(self, code):
        """Buscar concepto por código (for_payroll, plantilla, compañía de la importación)."""
        if not code or not str(code).strip():
            return None
        code_str = str(code).strip().upper()
        return self.env['hr.employee.recurring.concept'].search(
            [('code', '=ilike', code_str)] + self._concept_domain_base(),
            limit=1,
        )

    def _parse_numeric(self, val):
        """Parsear valor numérico. Retorna float o None."""
        if val is None or val == '':
            return None
        try:
            return float(str(val).replace(',', '.').strip())
        except (ValueError, TypeError):
            return None

    def action_import_file(self):
        """Procesar Excel: cada fila = una línea BD; mismo empleado puede repetirse con otro código."""
        if not self.file_data:
            raise UserError(_('Suba un archivo Excel antes de importar.'))
        if not OPENPYXL_AVAILABLE:
            raise UserError(_('Se requiere openpyxl. Instale: pip install openpyxl'))
        sheet = self._get_or_create_sheet()
        data = base64.b64decode(self.file_data)
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb['Importación'] if 'Importación' in wb.sheetnames else wb.active
        if not ws:
            raise UserError(_('El archivo no contiene hojas válidas.'))
        created_bd = updated_bd = skipped = 0
        errors = []
        log_lines = []
        num_cols = 9
        for row_num in range(2, ws.max_row + 1):
            row_data = []
            for c in range(1, num_cols + 1):
                cell = ws.cell(row=row_num, column=c)
                row_data.append(cell.value)
            row_dict = dict(zip(range(num_cols), row_data))
            emp = self._resolve_employee(row_dict, row_num)
            if not emp:
                nombre = str(row_data[COL_NOMBRE] or '').strip() if len(row_data) > COL_NOMBRE else ''
                nombre_str = f' "{nombre}"' if nombre else ''
                err = _('Fila %d%s: No se encontró empleado (employee_id o Identidad inválidos)') % (
                    row_num, nombre_str
                )
                errors.append(err)
                log_lines.append(err)
                continue
            code_val = str(row_data[COL_CODIGO_CONCEPTO] or '').strip() if len(row_data) > COL_CODIGO_CONCEPTO else ''
            amount = self._parse_numeric(row_data[COL_MONTO] if len(row_data) > COL_MONTO else None)

            if self.skip_empty and not code_val:
                if amount is None or amount == 0:
                    skipped += 1
                    continue
                err = _('Fila %d: Falta código de concepto pero el monto no es cero.') % row_num
                errors.append(err)
                log_lines.append(err)
                continue

            concept = self._resolve_concept(code_val)
            if not concept:
                err = _('Fila %d: Concepto "%s" no encontrado o no válido (for_payroll)') % (
                    row_num, code_val or '(vacío)'
                )
                errors.append(err)
                log_lines.append(err)
                continue
            if amount is None:
                err = _('Fila %d: Monto debe ser numérico') % row_num
                errors.append(err)
                log_lines.append(err)
                continue
            if self.skip_empty and amount == 0:
                skipped += 1
                continue
            line_bd = self.env['l10n.hn.payroll.line.bd'].search([
                ('parent_id', '=', sheet.id),
                ('employee_id', '=', emp.id),
                ('concept_id', '=', concept.id),
            ], limit=1)
            if line_bd:
                line_bd.write({'amount': amount})
                updated_bd += 1
            else:
                self.env['l10n.hn.payroll.line.bd'].create({
                    'parent_id': sheet.id,
                    'employee_id': emp.id,
                    'concept_id': concept.id,
                    'amount': amount,
                })
                created_bd += 1
        wb.close()
        summary = _('Importación completada.\n\n')
        summary += _('Creados BD: %d\n') % created_bd
        summary += _('Actualizados BD: %d\n') % updated_bd
        summary += _('Omitidos: %d\n') % skipped
        summary += _('Errores: %d\n') % len(errors)
        if errors:
            summary += _('\n--- Errores ---\n') + '\n'.join(errors[:20])
            if len(errors) > 20:
                summary += _('\n... y %d más (ver log)') % (len(errors) - 20)
        log_content = '\n'.join(log_lines) if log_lines else summary
        self.write({
            'state': 'done',
            'result_summary': summary,
            'result_log': base64.b64encode(log_content.encode('utf-8')),
            'result_log_filename': f'import_bd_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt',
        })
        sheet.message_post(body=_('Importación BD: %s') % summary)
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_download_log(self):
        """Descargar log de importación."""
        if not self.result_log:
            raise UserError(_('No hay log para descargar.'))
        attachment = self.env['ir.attachment'].create({
            'name': self.result_log_filename or 'import_log.txt',
            'type': 'binary',
            'datas': self.result_log,
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
