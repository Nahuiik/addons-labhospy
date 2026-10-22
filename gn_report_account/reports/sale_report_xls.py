# -*- coding: utf-8 -*-
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_is_zero
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
from datetime import datetime,timedelta
import io
import base64

class commissionReportXls(models.AbstractModel):
    _name = 'report.gn_report_account.commission_xls.xlsx'
    _description = 'Sales Commission Report XLS'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, lines):
        user_id = data.get('context').get('uid')
        company_name = self.env['res.users'].browse(user_id).company_id.name
        if data.get('values_in') == 'usd':
            values_in = 'USD'
        else:
            values_in = 'Moneda Local'
        
        if data.get('report_type') == 'detailed':
            detailed_inf = self.get_invoices(data.get('date_from'),data.get('date_to'),values_in,data.get('report_type'),data.get('state'),data.get('per_administrative'),data.get('per_indirect_cost'))
            invoices = detailed_inf.get('info_invoice_line')
            sellers = detailed_inf.get('info_sellers')
        else:
            inf = self.get_invoices(data.get('date_from'),data.get('date_to'),values_in,data.get('report_type'),data.get('state'), 0, 0)

        # Agrupar por branch_id
        if data.get('report_type') == 'detailed':
            invoices_by_branch = self._group_by_branch(invoices)
        else:
            invoices_by_branch = self._group_by_branch(inf)

        # Verificar si hay datos
        if not invoices_by_branch or all(not invoices for invoices in invoices_by_branch.values()):
            # Si no hay datos, crear una hoja con mensaje
            sheet = workbook.add_worksheet('Sin Datos')
            format1 = workbook.add_format({'font_size': 14, 'bottom': True, 'right': True, 'left': True, 'top': True, 'align': 'vcenter', 'bold': True})
            format11 = workbook.add_format({'font_size': 12, 'align': 'center', 'right': True, 'left': True, 'bottom': True, 'top': True, 'bold': True})
            sheet.merge_range('A1:D1', company_name, format1)
            sheet.merge_range('A2:D2', 'Reporte de Ventas', format11)
            sheet.write(4, 1, 'No se encontraron registros para los filtros seleccionados.', format11)
            return

        # Crear una hoja por cada branch
        for branch_id, branch_invoices in invoices_by_branch.items():
            # Solo crear hoja si hay facturas en este branch
            if not branch_invoices:
                continue
                
            branch_name = branch_invoices[0].get('branch_name', 'Sin Sucursal') if branch_invoices else 'Sin Sucursal'
            # Limpiar el nombre de la hoja (Excel tiene límite de 31 caracteres y no permite ciertos caracteres)
            sheet_name = branch_name[:31].replace('/', '-').replace('\\', '-').replace('?', '').replace('*', '').replace('[', '').replace(']', '').replace(':', '')
            if not sheet_name:
                sheet_name = 'Sucursal_%s' % branch_id if branch_id else 'Sin_Sucursal'
            
            if data.get('report_type') == 'detailed':
                self._write_detailed_sheet(workbook, sheet_name, company_name, values_in, branch_invoices, sellers, data.get('per_administrative'), data.get('per_indirect_cost'))
            else:
                self._write_summary_sheet(workbook, sheet_name, company_name, values_in, branch_invoices)

    def _group_by_branch(self, invoices):
        """Agrupa las facturas por branch_id"""
        grouped = {}
        for invoice in invoices:
            branch_id = invoice.get('branch_id', False)
            if branch_id not in grouped:
                grouped[branch_id] = []
            grouped[branch_id].append(invoice)
        return grouped

    def _write_detailed_sheet(self, workbook, sheet_name, company_name, values_in, invoices, sellers, per_administrative, per_indirect_cost):
        """Escribe el reporte detallado en una hoja"""
        sheet = workbook.add_worksheet(sheet_name)

        format1 = workbook.add_format({'font_size': 14, 'bottom': True, 'right': True, 'left': True, 'top': True, 'align': 'vcenter', 'bold': True})
        format11 = workbook.add_format({'font_size': 12, 'align': 'center', 'right': True, 'left': True, 'bottom': True, 'top': True, 'bold': True})
        format22 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
        format21 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True,'bg_color':'#F3F781'})
        format23 = workbook.add_format({'text_wrap': True,'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True,'bg_color':'#0B2161','font_color': 'white'})
        format24 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
        format25 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True,'bg_color':'#21610B','font_color': 'white'})
        format26 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True,'bg_color':'#000000','font_color': 'white'})
        format27 = workbook.add_format({'font_size': 11, 'align': 'center', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True,'bg_color':'#F7D358','font_color': 'black'})
        format28 = workbook.add_format({'font_size': 11, 'align': 'center', 'right': True, 'left': True,'bottom': False, 'top': True, 'bold': True,'bg_color':'#F7D358','font_color': 'black'})

        ########### NUMBER FORMAT #######################################
        format3 = workbook.add_format({'align':'right','left':False,'right':False,'bottom': False, 'top': False, 'font_size': 10,'num_format': '#,##0.00'})
        format4 = workbook.add_format({'align':'right','left':False,'right':False,'bottom': False, 'top': False, 'bold':True, 'font_size': 10,'num_format': '#,##0.00'})
        format5 = workbook.add_format({'align':'right','left':False,'right':False,'bottom': False, 'top': False, 'font_size': 10,'num_format': '.00' + '%'})
        font_size_8 = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8})
        red_mark = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8,
                                        'bg_color': 'red'})
        justify = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 12})
        font_size_8.set_align('center')
        justify.set_align('justify')
        format1.set_align('center')
        red_mark.set_align('center')

        sheet.set_column(0, 0, 3)
        sheet.set_column(1, 1, 15)
        sheet.set_column(2, 2, 17)
        sheet.set_column(3, 3, 30)
        sheet.set_column(4, 4, 30)
        sheet.set_column(5, 5, 35)
        sheet.set_column(6, 6, 35)
        sheet.set_column(7, 7, 10)
        sheet.set_column(8, 8, 15)
        sheet.set_column(9, 9, 15)
        sheet.set_column(10, 10, 13)
        sheet.set_column(11, 11, 13)
        sheet.set_column(12, 12, 13)
        sheet.set_column(13, 13, 13)
        sheet.set_column(14, 14, 13)
        sheet.set_column(15, 15, 13)
        sheet.set_column(16, 16, 13)
        sheet.set_column(17, 17, 13)
        sheet.set_column(18, 18, 13)
        sheet.set_column(19, 19, 13)
        sheet.set_column(20, 20, 13)
        sheet.set_column(21, 21, 13)
        sheet.set_column(22, 22, 13)
        sheet.set_column(23, 23, 13)
        sheet.set_column(24, 24, 13)
        sheet.set_column(25, 25, 13)
        sheet.set_column(26, 26, 13)
        sheet.set_column(27, 27, 13)

        sheet.merge_range('A1:AB1', company_name, format1)
        sheet.merge_range('A2:AB2', 'Reporte de Ventas', format11)
        
        sheet.write(3, 1, 'Valores en', format27)
        sheet.write(3, 2, values_in, format27)

        sheet.merge_range('J4:O4', 'PRECIO DE VENTA', format28)
        sheet.merge_range('P4:Q4', 'COSTOS', format28)
        sheet.merge_range('R4:S4', 'MARGEN BRUTO', format28)
        sheet.merge_range('T4:V4', 'GASTOS', format28)
        sheet.merge_range('W4:X4', 'UTILIDAD', format28)
        
        sheet.write(4, 0, '', format23)
        sheet.write(4, 1, 'Fecha', format23)
        sheet.write(4, 2, 'Numero Factura', format23)
        sheet.write(4, 3, 'Producto', format23)
        sheet.write(4, 4, 'Categoria', format23)
        sheet.write(4, 5, 'Cliente', format23)
        sheet.write(4, 6, 'Comercial', format23)
        sheet.write(4, 7, 'Cantidad', format23)
        sheet.write(4, 8, 'Precio Unitario', format23)
        sheet.write(4, 9, 'Gravado', format23)
        sheet.write(4, 10, 'Exento', format23)
        sheet.write(4, 11, 'Exonerado', format23)
        sheet.write(4, 12, 'Impuestos', format23)
        sheet.write(4, 13, 'Subtotal', format23)
        sheet.write(4, 14, 'Descuentos', format23)
        sheet.write(4, 15, 'Total', format25)
        sheet.write(4, 16, 'Costo Unitario', format23)
        sheet.write(4, 17, 'Costo Total', format23)
        sheet.write(4, 18, 'Utilidad Bruta', format25)
        sheet.write(4, 19, '% UB', format25)
        sheet.write(4, 20, 'Costos Indirectos', format25)
        sheet.write(4, 21, 'Administrativos', format25)
        sheet.write(4, 22, 'Gastos Totales', format25)
        sheet.write(4, 23, 'Utilidad', format25)
        sheet.write(4, 24, '% Neto', format25)
        sheet.write(4, 25, 'Estado', format25)
        
        pos = 5
        array_users = []
        partner_for_user = []
        t_total_cost = 0
        total_total = 0
        total_taxes = 0
        total_subtotal = 0
        total_bruta = 0
        total_discount = 0
        total_unit_cost = 0
        total_bruta = 0

        for invoice in invoices:
            vals = {
                'partner_id':invoice.get('partner_id'),
                'amount':invoice.get('amount'),
            }
            user_id = invoice.get('user_id')
            if user_id in array_users:
                partner_for_user[array_users.index(user_id)]['partners'].append(vals)
            else:
                array_users.append(user_id)
                partner_for_user.append({
                    'user_id': user_id,
                    'partners':[vals]
                })

            #total_disc += invoice.get('discount')
            total_taxes += invoice.get('taxes') or 0
            total_subtotal += invoice.get('subtotal') or 0
            t_total_cost += invoice.get('total_cost') or 0
            total_total += invoice.get('total') or 0
            total_bruta += invoice.get('u_bruta') or 0
            total_discount += invoice.get('discount') or 0
            total_unit_cost += invoice.get('unit_cost') or 0

            sheet.write(pos, 1, invoice.get('invoice_date'), format22)
            sheet.write(pos, 2, invoice.get('number'), format22)
            sheet.write(pos, 3, invoice.get('product'), format22)
            sheet.write(pos, 4, invoice.get('category'), format22)
            sheet.write(pos, 5, invoice.get('partner_name'), format22)
            sheet.write(pos, 6, invoice.get('seller'), format22)
            sheet.write(pos, 7, invoice.get('qty'), format24)
            sheet.write_number(pos, 8, invoice.get('price_unit') or 0, format3)
            sheet.write_number(pos, 9, invoice.get('taxed') or 0, format3)
            sheet.write_number(pos, 10, invoice.get('exempt') or 0, format3)
            sheet.write_number(pos, 11, invoice.get('exonerate') or 0, format3)
            sheet.write_number(pos, 12, invoice.get('taxes') or 0, format3)
            sheet.write_number(pos, 13, invoice.get('subtotal') or 0, format3)
            sheet.write_number(pos, 14, invoice.get('discount') or 0, format3)
            sheet.write_number(pos, 15, invoice.get('total') or 0, format3)
            sheet.write_number(pos, 16, invoice.get('unit_cost') or 0, format3)
            sheet.write_number(pos, 17, invoice.get('total_cost') or 0, format3)
            sheet.write_number(pos, 18, invoice.get('u_bruta') or 0, format3)
            sheet.write_number(pos, 19, invoice.get('ub') or 0, format3)
            sheet.write_number(pos, 20, invoice.get('ic') or 0, format3)
            sheet.write_number(pos, 21, invoice.get('administrative') or 0, format3)
            sheet.write_number(pos, 22, invoice.get('total_spends') or 0, format3)
            sheet.write_number(pos, 23, invoice.get('utility') or 0, format3)
            sheet.write_number(pos, 24, invoice.get('net') or 0, format3)
            sheet.write(pos, 25, invoice.get('state'), format24)
            pos+=1
        sheet.write_number(pos, 12, total_taxes or 0, format4)
        sheet.write_number(pos, 13, total_subtotal or 0, format4)
        sheet.write_number(pos, 14, total_discount or 0, format4)
        sheet.write_number(pos, 15, total_total or 0, format4)
        sheet.write_number(pos, 16, total_unit_cost or 0, format4)
        sheet.write_number(pos, 17, t_total_cost or 0, format4)
        sheet.write_number(pos, 18, total_bruta or 0, format4)

        ############################## HOJA DE SELLERS ###########################################
        # Filtrar sellers por branch_id
        branch_id = invoices[0].get('branch_id', False) if invoices else False
        branch_sellers = []
        if sellers and branch_id is not False:
            for seller in sellers:
                # Verificar si el seller tiene clientes del branch actual
                seller_clients = [c for c in seller.get('clients', []) if c.get('branch_id') == branch_id]
                if seller_clients:
                    branch_sellers.append({
                        'seller': seller.get('seller'),
                        'clients': seller_clients,
                        'user_id': seller.get('user_id'),
                    })
        elif sellers and branch_id is False:
            # Si no hay branch_id, mostrar todos los sellers (comportamiento original)
            branch_sellers = sellers
        
        if branch_sellers:
            sheet2_name = '%s - %s' % (sheet_name, 'Vendedores')
            # Limpiar el nombre de la hoja
            sheet2_name = sheet2_name[:31].replace('/', '-').replace('\\', '-').replace('?', '').replace('*', '').replace('[', '').replace(']', '').replace(':', '')
            sheet2 = workbook.add_worksheet(sheet2_name)

            sheet2.set_column(0, 0, 40)
            sheet2.set_column(1, 1, 40)
            sheet2.set_column(2, 2, 15)
            sheet2.set_column(3, 3, 15)
            sheet2.set_column(4, 4, 15)

            sheet2.write(4, 0, 'Vendedor', format23)
            sheet2.write(4, 1, 'Cliente', format23)
            sheet2.write(4, 2, 'Suma-Subtotal', format23)
            pos2 = 5
            total_subtotal = 0
            for seller in branch_sellers:
                sheet2.write(pos2, 0, seller.get('seller'), format22)
                pos2+=1
                clients_con = self.get_client(seller.get('clients'))
                amounts_values = self.get_values(seller.get('user_id'),partner_for_user) 
                for client in clients_con:
                    sheet2.write(pos2, 1, client.get('client'), format22)
                    sheet2.write_number(pos2, 2, client.get('subtotal') or 0, format3)
                    total_subtotal+=client.get('subtotal')
                    pos2+=1
                sheet2.write_number(pos2-len(amounts_values)-1, 2, total_subtotal , format4)

                total_subtotal = 0
                total_amount = 0

    def _write_summary_sheet(self, workbook, sheet_name, company_name, values_in, invoices):
        """Escribe el reporte resumido en una hoja"""
        sheet = workbook.add_worksheet(sheet_name)
        
        format1 = workbook.add_format({'font_size': 14, 'bottom': True, 'right': True, 'left': True, 'top': True, 'align': 'vcenter', 'bold': True})
        format11 = workbook.add_format({'font_size': 12, 'align': 'center', 'right': True, 'left': True, 'bottom': True, 'top': True, 'bold': True})
        format22 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
        format23 = workbook.add_format({'text_wrap': True,'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True,'bg_color':'#0B2161','font_color': 'white'})
        format27 = workbook.add_format({'font_size': 11, 'align': 'center', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True,'bg_color':'#F7D358','font_color': 'black'})
        format3 = workbook.add_format({'align':'right','left':False,'right':False,'bottom': False, 'top': False, 'font_size': 10,'num_format': '#,##0.00'})
        format4 = workbook.add_format({'align':'right','left':False,'right':False,'bottom': False, 'top': False, 'bold':True, 'font_size': 10,'num_format': '#,##0.00'})
        
        sheet.set_column(1, 1, 17)
        sheet.set_column(2, 2, 30)
        sheet.set_column(3, 3, 15)
        sheet.set_column(4, 4, 10)
        sheet.set_column(5, 5, 30)
        sheet.set_column(6, 6, 45)
        sheet.set_column(7, 7, 45)
        sheet.set_column(8, 8, 15)
        sheet.set_column(9, 9, 15)
        sheet.set_column(10, 10, 15)
        sheet.set_column(11, 11, 15)
        sheet.set_column(12, 12, 15)
        sheet.set_column(13, 13, 15)
        sheet.set_column(14, 14, 15)
        sheet.set_column(15, 15, 15)
        sheet.set_column(16, 16, 15)
        sheet.set_column(17, 17, 15)

        sheet.merge_range('A1:O1', company_name, format1)
        sheet.merge_range('A2:O2', 'Reporte de Ventas', format11)
        
        sheet.write(3, 1, 'Valores en', format27)
        sheet.write(3, 2, values_in, format27)
        
        sheet.write(4, 0, '', format23)
        sheet.write(4, 1, 'Numero Factura', format23)
        sheet.write(4, 2, 'Cliente', format23)
        sheet.write(4, 3, 'Fecha', format23)
        sheet.write(4, 4, 'Estado', format23)
        sheet.write(4, 5, 'Comercial', format23)
        sheet.write(4, 6, 'Numero de Pagos', format23)
        sheet.write(4, 7, 'Diarios de Pago', format23)
        sheet.write(4, 8, 'Total Pagado', format23)
        sheet.write(4, 9, 'Precio de Costo', format23)
        sheet.write(4, 10, 'Descuento', format23)
        sheet.write(4, 11, 'Exonerado', format23)
        sheet.write(4, 12, 'Exento', format23)
        sheet.write(4, 13, 'Gravado', format23)
        sheet.write(4, 14, 'Impuestos', format23)
        sheet.write(4, 15, 'Subtotal', format23)
        sheet.write(4, 16, 'Total', format23)
        sheet.write(4, 17, 'Residual', format23)

        pos = 5
        t_discount = 0
        t_taxes = 0
        t_subtotal = 0
        t_total = 0
        t_residual = 0
        t_pays = 0
        t_exonerate = 0
        t_exempt = 0
        t_taxed = 0

        for invoice_data in invoices:
                sheet.write(pos, 1, invoice_data.get('number'), format22)
                sheet.write(pos, 2, invoice_data.get('client'), format22)
                sheet.write(pos, 3, invoice_data.get('invoice_date'), format22)
                sheet.write(pos, 4, invoice_data.get('state'), format22)
                sheet.write(pos, 5, invoice_data.get('seller'), format22)
                sheet.write(pos, 6, invoice_data.get('pay_number'), format22)
                sheet.write(pos, 7, invoice_data.get('journal'), format22)
                sheet.write_number(pos, 8, invoice_data.get('pay_amounts') or 0, format3)
                sheet.write_number(pos, 9, invoice_data.get('cost_prices') or 0, format3)
                sheet.write_number(pos, 10, invoice_data.get('discount') or 0, format3)
                sheet.write_number(pos, 11, invoice_data.get('exonerate') or 0, format3)
                sheet.write_number(pos, 12, invoice_data.get('exempt') or 0, format3)
                sheet.write_number(pos, 13, invoice_data.get('taxed') or 0, format3)
                sheet.write_number(pos, 14, invoice_data.get('taxes') or 0, format3)
                sheet.write_number(pos, 15, invoice_data.get('subtotal') or 0, format3)
                sheet.write_number(pos, 16, invoice_data.get('total') or 0, format3)
                sheet.write_number(pos, 17, invoice_data.get('residual') or 0, format3)
                t_discount += invoice_data.get('discount') or 0
                t_taxes += invoice_data.get('taxes') or 0
                t_subtotal += invoice_data.get('subtotal') or 0
                t_total += invoice_data.get('total') or 0
                t_residual += invoice_data.get('residual') or 0
                t_pays += invoice_data.get('pay_amounts') or 0
                t_exonerate += invoice_data.get('exonerate') or 0
                t_exempt += invoice_data.get('exempt') or 0
                t_taxed += invoice_data.get('taxed') or 0
                pos+=1
        sheet.write_number(pos, 8, t_pays or 0, format4)
        sheet.write_number(pos, 10, t_discount or 0, format4)
        sheet.write_number(pos, 11, t_exonerate or 0, format4)
        sheet.write_number(pos, 12, t_exempt or 0, format4)
        sheet.write_number(pos, 13, t_taxed or 0, format4)
        sheet.write_number(pos, 14, t_taxes or 0, format4)
        sheet.write_number(pos, 15, t_subtotal or 0, format4)
        sheet.write_number(pos, 16, t_total or 0, format4)
        sheet.write_number(pos, 17, t_residual or 0, format4)

    def get_client(self,array_client):
        array = []
        info_client = []
        for client in array_client:
            if int(client.get('id')) in array:
                info_client[array.index(int(client.get('id')))]['subtotal']+=client.get('subtotal')
            else:
                array.append(int(client.get('id')))
                info_client.append({
                    'client':client.get('client'),
                    'subtotal':client.get('subtotal'),
                    'partner_id':client.get('id')
                })
        return info_client

    def get_values(self,user_id,partner_for_user):
        partners_values = []
        partner_ids = []
        for user in partner_for_user:
            if user.get('user_id') == user_id:
                for partner in user.get('partners'):
                    if partner.get('partner_id') in partner_ids:
                        partners_values[partner_ids.index(partner.get('partner_id'))]['amount']+=partner.get('amount')
                    else:
                        partner_ids.append(partner.get('partner_id'))
                        partners_values.append({
                            'amount':partner.get('amount'),
                            'partner_id':partner.get('partner_id'),
                            'user_id':user.get('user_id')
                        })
        return partners_values

    def get_journal_pays(self,lines):
        info_lines = []
        array_journal = []
        for pay in lines:
            if pay.journal_id.id in array_journal:
                pass
            else:
                array_journal.append(pay.journal_id.id)
                info_lines.append({
                    'journal':pay.journal_id.name
                })
        return info_lines
    
    def _compute_tax_details(self, invoice, line):
        price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
        quantity = line.quantity or 0.0
        taxes = line.tax_ids
        is_refund = invoice.move_type in ('in_refund', 'out_refund')
        if taxes:
            return taxes.compute_all(
                price_unit,
                currency=invoice.currency_id,
                quantity=quantity,
                product=line.product_id,
                partner=invoice.partner_id,
                is_refund=is_refund,
            )
        total = price_unit * quantity
        return {
            'taxes': [],
            'total_excluded': total,
            'total_included': total,
        }

    def get_taxes_and_base(self, invoice, line):
        tax_details = self._compute_tax_details(invoice, line)
        if not tax_details['taxes']:
            return 0.0
        return sum(tax.get('base', 0.0) for tax in tax_details['taxes'])
    
    def get_price_unit(self, invoice, line):
        tax_details = self._compute_tax_details(invoice, line)
        base_amount = tax_details['total_excluded']
        if line.quantity and base_amount > (line.price_unit * invoice.exch_rate * line.quantity):
            return base_amount / line.quantity
        return line.price_unit
        

    def get_taxes(self, invoice, line):
        tax_details = self._compute_tax_details(invoice, line)
        return sum(tax.get('amount', 0.0) for tax in tax_details['taxes'])

    def get_invoices(self, date_from, date_to, values_in, report_type, state, per_administrative, per_indirect_cost):
        allowed_company_ids = self.env.context.get('allowed_company_ids') or [self.env.company.id]
        domain = [
            ('move_type', 'in', ['out_invoice', 'out_refund', 'out_receipt']),
            ('state', '=', 'posted'),
            ('company_id', 'in', allowed_company_ids),
        ]
        account_invoice = self.env['account.move']
        info_invoice_line =[]
        info_sellers = []
        seller_ids = []
        date_from = fields.Date.to_date(date_from) if date_from else False
        date_to = fields.Date.to_date(date_to) if date_to else False
        if state == 'not_paid':
            domain.append(('payment_state', 'in',['not_paid', 'partial','in_payment']))
        elif state == 'paid':
            domain.append(('payment_state','=','paid'))


        obj_invoice = account_invoice.search(domain)
        if date_from:
            obj_invoice = obj_invoice.filtered(lambda m: (m.invoice_date or m.date) and (m.invoice_date or m.date) >= date_from)
        if date_to:
            obj_invoice = obj_invoice.filtered(lambda m: (m.invoice_date or m.date) and (m.invoice_date or m.date) <= date_to)
        days = ''
        if report_type == 'detailed':
            for invoice in obj_invoice:
                
                
                rate =  invoice.exch_rate
                cancel_date = self.get_cancel_date(invoice.payment_ids)
                if values_in == 'usd' and invoice.currency_id.name == 'USD':
                    invoice_subtotal = invoice.amount_untaxed
                elif values_in == 'usd' and not invoice.currency_id.name == 'USD':
                    invoice_subtotal = invoice.amount_untaxed*rate
                elif not values_in == 'usd' and invoice.currency_id.name == 'USD':
                    invoice_subtotal = invoice.amount_untaxed/rate
                elif not values_in == 'usd' and not invoice.currency_id.name == 'USD':
                    invoice_subtotal = invoice.amount_untaxed
                # Obtener branch_id y branch_name de forma segura
                branch_id = getattr(invoice, 'branch_id', False) and invoice.branch_id.id or False
                branch_name = getattr(invoice, 'branch_id', False) and invoice.branch_id.name or 'Sin Sucursal'
                
                values = {
                    'client':invoice.partner_id.name,
                    'subtotal':invoice_subtotal,
                    'id':invoice.partner_id.id,
                    'branch_id': branch_id
                }

                if invoice.user_id.id in seller_ids:
                    info_sellers[seller_ids.index(invoice.user_id.id)]['clients'].append(values)
                else:
                    seller_ids.append(invoice.user_id.id)
                    info_sellers.append({
                        'seller':invoice.user_id.name,
                        'clients':[values],
                        'user_id':invoice.user_id.id,
                        'partner_id':invoice.partner_id.id,
                    })
                
                if cancel_date:
                    days = self.get_days(cancel_date, invoice.invoice_date_due)
                count = 0

                for line in invoice.invoice_line_ids:
                    if line.display_type and line.display_type not in ('product', False):
                        continue

                    commission = 0
                    ic = 0
                    tax_15_per = 0
                    exempt_sale_amount = 0
                    exonerate_amount = 0
                    administrative = 0
                    total_spends = 0
                    amount = line.price_subtotal*(commission/100)

                    taxes = 0
                    tax_ids = line.tax_ids

                    if values_in == 'usd' and invoice.currency_id.name == 'USD':
                        cal_amount = amount
                        line_subtotal = round(line.price_subtotal,2)
                        line_price_unit = line.price_unit
                        line_discount = line.discount
                        p_list_1 = line.product_id.list_price
                        if p_list_1>line_price_unit:
                            dif = (p_list_1-line_price_unit)*-1
                        else:
                            dif = p_list_1-line_price_unit
                        if tax_ids:
                            if tax_ids[0].amount > 0:
                                taxes =  line_subtotal*0.15

                        tax_15_per = 0
                        exempt_sale_amount = 0
                        price = (line.price_unit * (1 - (line.discount or 0.0) / 100.0))
                        price = round(price * line.quantity,2)
                        for tax in tax_ids:
                            if tax.amount_type == 'percent' and tax.amount == 15:
                                tax_15_per = round(price* rate, 2)
                            if getattr(tax, 'is_exempt', False):
                                exempt_sale_amount = round(line_subtotal * rate, 2)
                            if getattr(tax, 'is_exonerate', False):
                                exonerate_amount = round(line_subtotal * rate, 2)
                    elif values_in == 'usd' and not invoice.currency_id.name == 'USD':
                        cal_amount = amount/rate
                        line_subtotal = line.price_subtotal/rate
                        line_price_unit = line.price_unit/rate
                        line_discount = line.discount/rate
                        p_list_1 = line.product_id.list_price
                        if p_list_1>line_price_unit:
                            dif = (p_list_1-line_price_unit)*-1
                        else:
                            dif = p_list_1-line_price_unit
                        if tax_ids:
                            if tax_ids[0].amount > 0:
                                taxes =  line_subtotal*0.15

                        tax_15_per = 0
                        exempt_sale_amount = 0
                        exonerate_amount = 0
                        price = (line.price_unit * (1 - (line.discount or 0.0) / 100.0))
                        price = round(price * line.quantity,2)
                        for tax in tax_ids:
                            if tax.amount_type == 'percent' and tax.amount == 15:
                                tax_15_per = round(price* rate, 2)
                            if getattr(tax, 'is_exempt', False):
                                exempt_sale_amount = round(line_subtotal * rate, 2)
                            if getattr(tax, 'is_exonerate', False):
                                exonerate_amount = round(line_subtotal * rate, 2)
                    elif not values_in == 'usd' and invoice.currency_id.name == 'USD':
                        cal_amount = amount*rate
                        line_subtotal = round(line.price_subtotal,2)
                        line_discount = line.discount*rate
                        line_price_unit = self.get_price_unit(invoice, line)
                        p_list_1 = line.product_id.list_price*rate                        
                        if p_list_1>line_price_unit:
                            dif = (p_list_1-line_price_unit)*-1
                        else:
                            dif = p_list_1-line_price_unit
                        taxes = self.get_taxes(invoice,line)

                        tax_15_per = 0
                        exempt_sale_amount = 0
                        exonerate_amount = 0
                        price = round((line.price_unit * (1 - (line.discount or 0.0) / 100.0)),2)
                        price = round(line.price_subtotal,2)
                        for tax in tax_ids:
                            if tax.amount_type == 'percent' and tax.amount == 15:
                                tax_15_per = self.get_taxes_and_base(invoice, line)
                                line_subtotal = tax_15_per 
                            if getattr(tax, 'is_exempt', False):
                                exempt_sale_amount = self.get_taxes_and_base(invoice, line)
                                line_subtotal = exempt_sale_amount
                            if getattr(tax, 'is_exonerate', False):
                                exonerate_amount = self.get_taxes_and_base(invoice, line)
                                line_subtotal = exonerate_amount
                    elif not values_in == 'usd' and not invoice.currency_id.name == 'USD':
                        rate =  self.get_rate(invoice.invoice_date,'USD')
                        cal_amount = amount
                        line_subtotal = line.price_subtotal
                        line_price_unit = line.price_unit
                        line_discount = line.discount
                        p_list_1 = line.product_id.list_price*1
                        if p_list_1>line_price_unit:
                            dif = (p_list_1-line_price_unit)*-1
                        else:
                            dif = p_list_1-line_price_unit
                        if tax_ids:
                            taxes = self.get_taxes(invoice,line)
                            for tax in tax_ids:
                                if tax.amount_type == 'percent' and tax.amount == 15:
                                    tax_15_per = self.get_taxes_and_base(invoice, line)
                                    line_subtotal = tax_15_per 
                                if getattr(tax, 'is_exempt', False):
                                    exempt_sale_amount = self.get_taxes_and_base(invoice, line)
                                    line_subtotal = exempt_sale_amount
                                if getattr(tax, 'is_exonerate', False):
                                    exonerate_amount = self.get_taxes_and_base(invoice, line)
                                    line_subtotal = exonerate_amount

                    p_list_1 = line.product_id.list_price
                    dif = p_list_1 - line.price_unit
                    if p_list_1 > line.price_unit:
                        dif = (p_list_1-line_price_unit)*-1

                    if invoice.payment_state == 'paid':
                        state = 'Pagada'
                    elif invoice.payment_state == 'not_paid':
                        state = 'Sin Pagar'
                    elif invoice.payment_state == 'in_payment':
                        state = 'En Proceso de Pago'
                    elif invoice.payment_state == 'partial':
                        state = 'Parcialmente Pagado'

                    unit_cost = line.product_id.standard_price
                    if line.product_id.type == 'service':
                        unit_cost = 0

                    discount = 0
                    if (line.discount or 0.0) > 0:
                        discount = line.quantity * line.price_unit * (line.discount or 0.0) / 100.0
                    
                    total = line_subtotal + taxes# - discount
                    total_cost = line.quantity * unit_cost
                    u_bruta = total - total_cost

                    ic = line_subtotal * (per_indirect_cost/100)
                    administrative = line_subtotal * (per_administrative/100)
                    total_spends = ic + administrative
                    utility = u_bruta - total_spends

                    if float_is_zero(total, 2):
                        net = 0
                        ub = 0
                    else:
                        net = utility / total
                        ub = u_bruta / total

                    # Obtener branch_id y branch_name de forma segura
                    branch_id = getattr(invoice, 'branch_id', False) and invoice.branch_id.id or False
                    branch_name = getattr(invoice, 'branch_id', False) and invoice.branch_id.name or 'Sin Sucursal'
                    
                    # Obtener categoría del producto
                    category = line.product_id.categ_id.name if line.product_id and line.product_id.categ_id else ''
                    
                    info_invoice_line.append({
                        'number': invoice.name,
                        'product': line.product_id.name or line.name or '',
                        'partner_name': invoice.partner_id.name,
                        'invoice_date': self.change_format(invoice.invoice_date),
                        'seller': invoice.user_id.name,
                        'qty': line.quantity,
                        'discount': discount,
                        'price_unit': line_price_unit,
                        'cost_price': line_subtotal * (70/100),
                        'subtotal': line_subtotal,
                        'total': total,
                        'u_bruta': u_bruta,
                        'ub': ub * 100,
                        'des': str(line.discount) + '%',
                        'cancel_date': self.get_cancel_date(invoice.payment_ids),
                        'days': days,
                        'amount': cal_amount,
                        'partner_id': invoice.partner_id.id,
                        'user_id': invoice.user_id.id,
                        'rate': rate,
                        'taxes': taxes,
                        'state': state,
                        'rtn': invoice.partner_id.rtn or '',
                        'cai': invoice.cai_shot,
                        'taxed': tax_15_per,
                        'exempt': exempt_sale_amount,
                        'exonerate': exonerate_amount,
                        'ic': ic,
                        'administrative': administrative,
                        'total_spends': total_spends,
                        'utility': utility,
                        'net': net * 100,
                        'category': category,
                        'total_cost': total_cost,
                        'unit_cost': unit_cost,
                        'branch_id': branch_id,
                        'branch_name': branch_name,
                    })
                    days = ''
                count += 1
            return {'info_invoice_line':info_invoice_line, 'info_sellers':info_sellers}
        else:
            info = []
            for invoice in obj_invoice:
                if invoice.payment_state == 'paid':
                    state = 'Pagada'
                elif invoice.payment_state == 'not_paid':
                    state = 'Sin Pagar'
                elif invoice.payment_state == 'in_payment':
                    state = 'En Proceso de Pago'
                elif invoice.payment_state == 'partial':
                    state = 'Parcialmente Pagado'

                cost_prices = sum(invoice.invoice_line_ids.mapped('price_subtotal'))
                discount_amount = sum(invoice.invoice_line_ids.mapped(lambda l: l.price_unit * (l.discount or 0.0) / 100.0 * l.quantity))

                rate =  invoice.exch_rate
                invoice_subtotal = 0
                invoice_amount_total = 0
                invoice_amount_residual = 0
                invoice_amount_tax = 0
                invoice_exonerate_amount = 0
                invoice_exempt_sale_amount = 0
                invoice_amount_tax_15_per = 0

                if invoice.currency_id.name == 'HNL':
                    invoice_subtotal = invoice.amount_untaxed
                    invoice_amount_total = invoice.amount_total
                    invoice_amount_residual = invoice.amount_residual
                    invoice_amount_tax = invoice.amount_tax
                    invoice_exonerate_amount = invoice.exonerate_amount
                    invoice_exempt_sale_amount = invoice.exempt_sale_amount
                    invoice_amount_tax_15_per = invoice.amount_tax_15_per
                else:
                    invoice_subtotal = invoice.amount_untaxed_signed
                    invoice_amount_total = invoice.amount_local
                    invoice_amount_residual = invoice.amount_residual_signed
                    invoice_amount_tax = invoice.amount_tax_signed
                    invoice_exonerate_amount = invoice.exonerate_amount * rate
                    invoice_exempt_sale_amount = invoice.exempt_sale_amount * rate
                    invoice_amount_tax_15_per = invoice.amount_untaxed_signed
                    cost_prices = cost_prices * rate
                    discount_amount = discount_amount * rate

                journals = ''
                pay_numbers = ''
                pay_amounts = 0

                payments_vals = invoice.sudo().invoice_payments_widget and invoice.sudo().invoice_payments_widget['content'] or []
                if payments_vals:
                    journals = ', '.join(map(lambda p: p['journal_name'], payments_vals))
                    pay_numbers = ', '.join(map(lambda p: p['ref'], payments_vals))
                    pay_amounts = sum(map(lambda p: p['amount'], payments_vals))
                
                # Obtener branch_id y branch_name de forma segura
                branch_id = getattr(invoice, 'branch_id', False) and invoice.branch_id.id or False
                branch_name = getattr(invoice, 'branch_id', False) and invoice.branch_id.name or 'Sin Sucursal'
                
                info.append({
                    'number': invoice.name or invoice.number,
                    'client': invoice.partner_id.name or '',
                    'invoice_date': self.change_format(invoice.invoice_date),
                    'seller': invoice.user_id.name,
                    'discount': discount_amount,
                    'taxes': invoice_amount_tax,
                    'subtotal': invoice_subtotal,
                    'total': invoice_amount_total,
                    'residual': invoice_amount_residual,
                    'journal': journals,
                    'state': state,
                    'pay_number': pay_numbers,
                    'pay_amounts': pay_amounts,
                    'cost_prices': cost_prices * (70/100),
                    'exonerate': invoice_exonerate_amount,
                    'exempt': invoice_exempt_sale_amount,
                    'taxed': invoice_amount_tax_15_per,
                    'branch_id': branch_id,
                    'branch_name': branch_name,
                })
            return info

    def get_rate(self,date,name):
        currency = self.env['res.currency'].search([('name','=',name)])
        date2 = date
        change_rate = 1
        if len(currency.rate_ids)>0:
            day = timedelta(days=-1)
            before_day = date2+day
            today_currency = currency.rate_ids.filtered(lambda r: datetime.strptime(str(r.name), '%Y-%m-%d').date() == before_day)
            if today_currency:
                if len(today_currency)>1:
                    for rate in today_currency:
                        change_rate = rate.rate
                else:
                    change_rate = today_currency.rate
            else:
                other_rate = currency.rate_ids.filtered(lambda r: datetime.strptime(str(r.name), '%Y-%m-%d').date() < before_day)
                for other in other_rate:
                    change_rate = other.rate
                    return change_rate
            return change_rate

    def get_days(self, cancel_date, date_due):
        cancel = fields.Date.to_date(cancel_date) if cancel_date else fields.Date.context_today(self)
        due = fields.Date.to_date(date_due) if date_due else cancel
        return (cancel - due).days
    
    def get_cancel_date(self,payments):
        dates = [fields.Date.to_date(pay.payment_date) for pay in payments if pay.payment_date]
        return dates and max(dates) or False

    def change_format(self, date):
        if not date:
            return ''
        if isinstance(date, str): 
            date = datetime.strptime(date, '%Y-%m-%d').date()
        return date.strftime('%d/%m/%Y')
