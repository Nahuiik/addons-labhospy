# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date, datetime
from dateutil.relativedelta import relativedelta


class L10nHnIsrAuditReport(models.TransientModel):
    """ISR Audit Report Wizard"""
    _name = 'l10n.hn.isr.audit.report'
    _description = 'ISR Audit Report'

    report_type = fields.Selection([
        ('annual_summary', 'Resumen Anual por Empleado'),
        ('monthly_comparative', 'Comparativo Mensual'),
        ('projection_vs_real', 'Proyección vs Real'),
        ('employee_detail', 'Detalle por Empleado'),
    ], string='Tipo de Reporte', required=True, default='annual_summary')
    
    employee_ids = fields.Many2many('hr.employee', string='Empleados',
                                    help='Dejar vacío para todos los empleados')
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.company)
    year = fields.Integer(string='Año', required=True,
                         default=lambda self: fields.Date.today().year)
    month_from = fields.Integer(string='Mes Desde', default=1)
    month_to = fields.Integer(string='Mes Hasta', default=12)
    
    def action_generate_report(self):
        """Generate the selected report"""
        self.ensure_one()
        
        if self.report_type == 'annual_summary':
            return self._generate_annual_summary()
        elif self.report_type == 'monthly_comparative':
            return self._generate_monthly_comparative()
        elif self.report_type == 'projection_vs_real':
            return self._generate_projection_vs_real()
        elif self.report_type == 'employee_detail':
            return self._generate_employee_detail()
    
    def _generate_annual_summary(self):
        """Generate annual summary report by employee"""
        domain = [
            ('company_id', '=', self.company_id.id),
            ('year', '=', self.year),
        ]
        if self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))
        
        # Create action to show results grouped by employee
        return {
            'name': _('Resumen Anual ISR %s') % self.year,
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.hn.isr.audit',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {
                'search_default_group_employee': 1,
                'group_by': ['employee_id'],
            },
        }
    
    def _generate_monthly_comparative(self):
        """Generate monthly comparative report"""
        domain = [
            ('company_id', '=', self.company_id.id),
            ('year', '=', self.year),
        ]
        if self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))
        
        # Filter by month range
        if self.month_from > 0:
            date_from = date(self.year, self.month_from, 1)
            domain.append(('period_start', '>=', date_from))
        if self.month_to > 0:
            date_to = date(self.year, self.month_to, 28) + relativedelta(months=1) - relativedelta(days=1)
            domain.append(('period_end', '<=', date_to))
        
        return {
            'name': _('Comparativo Mensual ISR %s') % self.year,
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.hn.isr.audit',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {
                'search_default_group_period': 1,
                'group_by': ['period_year_month'],
            },
        }
    
    def _generate_projection_vs_real(self):
        """Generate projection vs real report"""
        domain = [
            ('company_id', '=', self.company_id.id),
            ('year', '=', self.year),
        ]
        if self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))
        
        return {
            'name': _('Proyección vs Real ISR %s') % self.year,
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.hn.isr.audit',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {
                'search_default_group_employee': 1,
            },
        }
    
    def _generate_employee_detail(self):
        """Generate detailed report for selected employees"""
        if not self.employee_ids:
            raise UserError(_('Debe seleccionar al menos un empleado para el reporte de detalle.'))
        
        domain = [
            ('company_id', '=', self.company_id.id),
            ('year', '=', self.year),
            ('employee_id', 'in', self.employee_ids.ids),
        ]
        
        return {
            'name': _('Detalle ISR por Empleado %s') % self.year,
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.hn.isr.audit',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {
                'group_by': ['employee_id', 'period_start'],
            },
        }
    
    def action_export_excel(self):
        """Export audit data to Excel"""
        import io
        import base64
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill
        except ImportError:
            raise UserError(_('openpyxl library is required. Please install it: pip install openpyxl'))
        
        domain = [
            ('company_id', '=', self.company_id.id),
            ('year', '=', self.year),
        ]
        if self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))
        
        audits = self.env['l10n.hn.isr.audit'].search(domain, order='employee_id, period_start')
        
        if not audits:
            raise UserError(_('No hay registros de auditoría para exportar.'))
        
        # Create workbook
        wb = Workbook()
        ws = wb.active
        ws.title = f"ISR Audit {self.year}"
        
        # Header style
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        header_alignment = Alignment(horizontal="center", vertical="center")
        
        # Headers
        headers = [
            'Empleado', 'Año', 'Período Inicio', 'Período Fin',
            'Ingreso Básico YTD', 'Ingreso Variable YTD', '13vo Mes Gravable', '14to Mes Gravable',
            'Total Ingreso YTD', 'Deducciones Nómina YTD', 'Deducciones Declaradas YTD', 'Gastos Médicos YTD',
            'Total Deducciones YTD', 'Proyección Ingreso Anual', 'Proyección Deducciones Anual',
            'Base Gravable Proyectada', 'ISR Anual Calculado', 'ISR Retenido YTD', 'Saldo ISR',
            'ISR Período', 'Períodos Restantes'
        ]
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment
        
        # Data
        for row, audit in enumerate(audits, 2):
            ws.cell(row=row, column=1, value=audit.employee_id.name or '')
            ws.cell(row=row, column=2, value=audit.year)
            ws.cell(row=row, column=3, value=audit.period_start.strftime('%Y-%m-%d') if audit.period_start else '')
            ws.cell(row=row, column=4, value=audit.period_end.strftime('%Y-%m-%d') if audit.period_end else '')
            ws.cell(row=row, column=5, value=float(audit.basic_income_ytd))
            ws.cell(row=row, column=6, value=float(audit.variable_income_ytd))
            ws.cell(row=row, column=7, value=float(audit.thirteenth_month_taxable))
            ws.cell(row=row, column=8, value=float(audit.fourteenth_month_taxable))
            ws.cell(row=row, column=9, value=float(audit.total_taxable_income_ytd))
            ws.cell(row=row, column=10, value=float(audit.payroll_deductions_ytd))
            ws.cell(row=row, column=11, value=float(audit.employee_declared_deductions_ytd))
            ws.cell(row=row, column=12, value=float(audit.medical_expenses_ytd))
            ws.cell(row=row, column=13, value=float(audit.total_deductions_ytd))
            ws.cell(row=row, column=14, value=float(audit.projected_annual_income))
            ws.cell(row=row, column=15, value=float(audit.projected_annual_deductions))
            ws.cell(row=row, column=16, value=float(audit.projected_taxable_base))
            ws.cell(row=row, column=17, value=float(audit.isr_annual_calculated))
            ws.cell(row=row, column=18, value=float(audit.isr_retained_ytd))
            ws.cell(row=row, column=19, value=float(audit.isr_balance))
            ws.cell(row=row, column=20, value=float(audit.isr_period_amount))
            ws.cell(row=row, column=21, value=audit.periods_remaining)
        
        # Auto-adjust column widths
        column_letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        for col in range(1, min(len(headers) + 1, 27)):
            if col <= 26:
                ws.column_dimensions[column_letters[col-1]].width = 18
        
        # Save to bytes
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        # Create attachment
        filename = f'ISR_Audit_{self.year}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': 'l10n.hn.isr.audit.report',
            'res_id': self.id,
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
