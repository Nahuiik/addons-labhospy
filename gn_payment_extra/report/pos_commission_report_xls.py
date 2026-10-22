# -*- coding: utf-8 -*-
from odoo import models


class PosCommissionReportXls(models.AbstractModel):
    _name = 'report.gn_payment_extra.pos_commission_report_xls'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Reporte de Comisiones POS XLSX'

    def generate_xlsx_report(self, workbook, data, wizards):
        for wizard in wizards:
            report_data = wizard._get_report_data()
            
            # Crear hoja
            sheet = workbook.add_worksheet('Comisiones POS')
            
            # Formatos
            title_format = workbook.add_format({
                'bold': True,
                'font_size': 14,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#4472C4',
                'font_color': 'white',
            })
            header_format = workbook.add_format({
                'bold': True,
                'font_size': 10,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#D9E1F2',
                'border': 1,
            })
            agreement_format = workbook.add_format({
                'bold': True,
                'font_size': 11,
                'bg_color': '#FFC000',
                'border': 1,
            })
            cell_format = workbook.add_format({
                'font_size': 10,
                'border': 1,
            })
            money_format = workbook.add_format({
                'font_size': 10,
                'border': 1,
                'num_format': '$ #,##0.00',
            })
            percent_format = workbook.add_format({
                'font_size': 10,
                'border': 1,
                'num_format': '0.00%',
            })
            subtotal_format = workbook.add_format({
                'bold': True,
                'font_size': 10,
                'bg_color': '#E2EFDA',
                'border': 1,
            })
            subtotal_money_format = workbook.add_format({
                'bold': True,
                'font_size': 10,
                'bg_color': '#E2EFDA',
                'border': 1,
                'num_format': '$ #,##0.00',
            })
            total_format = workbook.add_format({
                'bold': True,
                'font_size': 11,
                'bg_color': '#4472C4',
                'font_color': 'white',
                'border': 1,
            })
            total_money_format = workbook.add_format({
                'bold': True,
                'font_size': 11,
                'bg_color': '#4472C4',
                'font_color': 'white',
                'border': 1,
                'num_format': '$ #,##0.00',
            })
            
            # Configurar anchos de columna
            sheet.set_column('A:A', 12)  # Fecha
            sheet.set_column('B:B', 15)  # Referencia
            sheet.set_column('C:C', 30)  # Cliente
            sheet.set_column('D:D', 20)  # Tipo Método
            sheet.set_column('E:E', 8)   # Meses
            sheet.set_column('F:F', 10)  # % Comisión
            sheet.set_column('G:G', 14)  # Ventas
            sheet.set_column('H:H', 14)  # Monto sin IVA
            sheet.set_column('I:I', 12)  # IVA
            sheet.set_column('J:J', 12)  # Comisión
            sheet.set_column('K:K', 12)  # IVA Com 13%
            sheet.set_column('L:L', 12)  # Retención
            sheet.set_column('M:M', 14)  # Total Deduc
            sheet.set_column('N:N', 14)  # Monto a Recibir
            
            row = 0
            
            # Título
            sheet.merge_range(row, 0, row, 13, 'REPORTE DE COMISIONES POR POS', title_format)
            row += 1
            
            # Información del reporte
            sheet.write(row, 0, f"Compañía: {report_data['company'].name}", cell_format)
            row += 1
            sheet.write(row, 0, f"Período: {report_data['date_from']} - {report_data['date_to']}", cell_format)
            row += 2
            
            # Encabezados
            headers = [
                'Fecha', 'Referencia', 'Cliente', 'Tipo Método', 'Meses', '% Comisión',
                'Ventas', 'Monto sin IVA', 'IVA', 'Comisión', 'IVA Com 13%',
                'Retención', 'Total Deduc.', 'Monto a Recibir'
            ]
            for col, header in enumerate(headers):
                sheet.write(row, col, header, header_format)
            row += 1
            
            # Datos por convenio
            for agreement_name, agreement_data in report_data['data'].items():
                # Nombre del convenio
                sheet.merge_range(row, 0, row, 13, f"CONVENIO: {agreement_name}", agreement_format)
                row += 1
                
                # Líneas del convenio
                for line in agreement_data['lines']:
                    sheet.write(row, 0, str(line['date']), cell_format)
                    sheet.write(row, 1, line['name'], cell_format)
                    sheet.write(row, 2, line['partner'], cell_format)
                    sheet.write(row, 3, line['method_type'], cell_format)
                    sheet.write(row, 4, line['months'], cell_format)
                    sheet.write(row, 5, line['commission_pct'] / 100, percent_format)
                    sheet.write(row, 6, line['amount'], money_format)
                    sheet.write(row, 7, line['amount_without_vat'], money_format)
                    sheet.write(row, 8, line['vat_amount'], money_format)
                    sheet.write(row, 9, line['commission_amount'], money_format)
                    sheet.write(row, 10, line['commission_vat_amount'], money_format)
                    sheet.write(row, 11, line['retention_amount'], money_format)
                    sheet.write(row, 12, line['total_deductions'], money_format)
                    sheet.write(row, 13, line['amount_to_receive'], money_format)
                    row += 1
                
                # Subtotal del convenio
                subtotals = agreement_data['subtotals']
                sheet.write(row, 0, f"Subtotal {agreement_name}", subtotal_format)
                sheet.write(row, 1, '', subtotal_format)
                sheet.write(row, 2, '', subtotal_format)
                sheet.write(row, 3, '', subtotal_format)
                sheet.write(row, 4, subtotals['count'], subtotal_format)
                sheet.write(row, 5, '', subtotal_format)
                sheet.write(row, 6, subtotals['amount'], subtotal_money_format)
                sheet.write(row, 7, subtotals['without_vat'], subtotal_money_format)
                sheet.write(row, 8, subtotals['vat'], subtotal_money_format)
                sheet.write(row, 9, subtotals['commission'], subtotal_money_format)
                sheet.write(row, 10, subtotals['commission_vat'], subtotal_money_format)
                sheet.write(row, 11, subtotals['retention'], subtotal_money_format)
                sheet.write(row, 12, subtotals['deductions'], subtotal_money_format)
                sheet.write(row, 13, subtotals['to_receive'], subtotal_money_format)
                row += 2
            
            # Total general
            totals = report_data['totals']
            sheet.write(row, 0, 'TOTAL GENERAL', total_format)
            sheet.write(row, 1, '', total_format)
            sheet.write(row, 2, '', total_format)
            sheet.write(row, 3, '', total_format)
            sheet.write(row, 4, totals['payment_count'], total_format)
            sheet.write(row, 5, '', total_format)
            sheet.write(row, 6, totals['total_amount'], total_money_format)
            sheet.write(row, 7, totals['total_without_vat'], total_money_format)
            sheet.write(row, 8, totals['total_vat'], total_money_format)
            sheet.write(row, 9, totals['total_commission'], total_money_format)
            sheet.write(row, 10, totals['total_commission_vat'], total_money_format)
            sheet.write(row, 11, totals['total_retention'], total_money_format)
            sheet.write(row, 12, totals['total_deductions'], total_money_format)
            sheet.write(row, 13, totals['total_to_receive'], total_money_format)
