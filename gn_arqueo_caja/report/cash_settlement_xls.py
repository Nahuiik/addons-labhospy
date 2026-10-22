# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
import io
import base64
from datetime import datetime,timedelta

class cashSettlementXls(models.AbstractModel):
    _name = 'report.gn_arqueo_caja.cash_settlement_xls.xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Cash Settlement XLS Report'

    def generate_xlsx_report(self, workbook, data, lines):
        cashiers = self.get_invoices(data.get('date_from'),data.get('date_to'),data.get('cashier_ids'))
        
        format1 = workbook.add_format({'font_size': 14, 'bottom': True, 'right': True, 'left': True, 'top': True, 'align': 'vcenter', 'bold': True})
        format11 = workbook.add_format({'font_size': 12, 'align': 'center', 'right': True, 'left': True, 'bottom': True, 'top': True, 'bold': True})
        format22 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
        format21 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True,'bg_color':'#20964F'})
        format23 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True,'bg_color':'#000000','font_color': 'white'})
        format24 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True})
        format25 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': False, 'left': False,'bottom': False, 'top': True, 'bold': False})
        format26 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': False})
        ########### NUMBER FORMAT #######################################
        format3 = workbook.add_format({'align':'right','left':False,'right':False,'bottom': False, 'top': False, 'font_size': 10,'num_format': '#,##0.00'})
        format4 = workbook.add_format({'align':'right','left':False,'right':False,'bottom': False, 'top': False, 'bold':True ,'font_size': 10,'num_format': '#,##0.00'})
        format5 = workbook.add_format({'align':'right','left':True,'right':True,'bottom': True, 'top': True, 'bold':True ,'font_size': 10,'num_format': '#,##0.00'})
        font_size_8 = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8})
        red_mark = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8,
                                        'bg_color': 'red'})
        justify = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 12})
        font_size_8.set_align('center')
        justify.set_align('justify')
        format1.set_align('center')
        red_mark.set_align('center')


        for cash in cashiers:
            sheet = workbook.add_worksheet(cash.get('cashier'))
            sheet.set_column(0, 0, 5)   # #
            sheet.set_column(1, 1, 12)  # Fecha
            sheet.set_column(2, 2, 20)  # Número Pago
            sheet.set_column(3, 3, 25)  # Fecha y Hora Creación
            sheet.set_column(4, 4, 25)  # Diario Pago
            sheet.set_column(5, 5, 30)  # Cliente
            sheet.set_column(6, 6, 15)  # Total

            sheet.merge_range('D4:G4', self.env.user.company_id.name, format1)
            sheet.merge_range('D5:G5', 'ARQUEO DE CAJA DIARIO', format11)
            
            buf_image = io.BytesIO(base64.b64decode(self.env.user.company_id.logo))
            sheet.insert_image('C1', "any_name.png", {'image_data': buf_image, 'x_scale': 0.5, 'y_scale': 0.5})
            
            sheet.write(6, 3, 'Desde: %s' % (data.get('date_from')), format22)
            sheet.write(6, 4, 'Hasta: %s' % (data.get('date_to')), format22)
            sheet.write(6, 5, 'Cajero: %s' % (cash.get('cashier')), format22)

            pos = 9
            total = 0
            num = 1
            sheet.write(8, 0, '#', format21)
            sheet.write(8, 1, 'Fecha de Pago', format21)
            sheet.write(8, 2, 'Número de Pago', format21)
            sheet.write(8, 3, 'Fecha y Hora de Creación', format21)
            sheet.write(8, 4, 'Diario de Pago', format21)
            sheet.write(8, 5, 'Cliente', format21)
            sheet.write(8, 6, 'Total', format21)
            for invoice in cash.get('info', []):
                sheet.write(pos, 0, num, format22)
                sheet.write(pos, 1, invoice.get('date'), format22)
                sheet.write(pos, 2, invoice.get('number'), format22)
                sheet.write(pos, 3, invoice.get('create_date'), format22)
                sheet.write(pos, 4, invoice.get('journal'), format22)
                sheet.write(pos, 5, invoice.get('partner'), format22)
                sheet.write_number(pos, 6, invoice.get('total'), format3)
                total += invoice.get('total')
                pos += 1
                num += 1

            sheet.write_number(pos, 6, total, format4)
            pos += 3
            for jour in cash.get('journals', []):
                sheet.write(pos, 2, jour.get('journal'), format23)
                sheet.write_number(pos, 3, jour.get('total'), format5)
                pos += 1
            num = 1

            sheet.write(pos+2, 1, 'Observaciones', format24)
            loc = 'C'+str(pos+3)+':F'+str(pos+3)
            sheet.merge_range(loc, '', format26)        

            loc = 'C'+str(pos+5)+':C'+str(pos+7)
            sheet.merge_range(loc, '', format22)
            sheet.write(pos+7, 2, 'Firma del Cajero', format25)

            loc = 'E'+str(pos+5)+':E'+str(pos+7)
            sheet.merge_range(loc, '', format22)
            sheet.write(pos+7, 4, 'Firma del Supervisor', format25)

            ####################### Facturas Anuladas ########################################
            if cash.get('cancel_invoice') and len(cash.get('cancel_invoice')) > 0:
                sheet2 = workbook.add_worksheet('Facturas Anuladas %s' % (cash.get('cashier')))
                sheet2.set_column(0, 0, 5)   # #
                sheet2.set_column(1, 1, 20)  # Número Factura
                sheet2.set_column(2, 2, 25)  # Cliente
                sheet2.set_column(3, 3, 15)  # Fecha Factura
                sheet2.set_column(4, 4, 15)  # Total

                sheet2.merge_range('C4:E4', self.env.user.company_id.name, format1)
                sheet2.merge_range('C5:E5', 'FACTURAS ANULADAS', format11)
                
                buf_image = io.BytesIO(base64.b64decode(self.env.user.company_id.logo))
                sheet2.insert_image('B1', "any_name.png", {'image_data': buf_image, 'x_scale': 0.2, 'y_scale': 0.2})
                
                sheet2.write(6, 2, 'Desde: %s' % (data.get('date_from')), format22)
                sheet2.write(6, 3, 'Hasta: %s' % (data.get('date_to')), format22)
                sheet2.write(6, 4, 'Cajero: %s' % (cash.get('cashier')), format22)

                pos = 9
                total = 0
                num = 1
                sheet2.write(8, 0, '#', format21)
                sheet2.write(8, 1, 'Número de Factura', format21)
                sheet2.write(8, 2, 'Cliente', format21)
                sheet2.write(8, 3, 'Fecha de Factura', format21)
                sheet2.write(8, 4, 'Total', format21)
                for cancel in cash.get('cancel_invoice', []):
                    sheet2.write(pos, 0, num, format22)
                    sheet2.write(pos, 1, cancel.get('number'), format22)
                    sheet2.write(pos, 2, cancel.get('partner'), format22)
                    sheet2.write(pos, 3, cancel.get('date_invoice'), format22)
                    sheet2.write_number(pos, 4, cancel.get('total'), format3)
                    total += cancel.get('total', 0)
                    pos += 1
                    num += 1
                
                # Total
                sheet2.write(pos, 3, 'Total:', format24)
                sheet2.write_number(pos, 4, total, format4)

            ####################### Facturas Abiertas ########################################
            if cash.get('open_invoice') and len(cash.get('open_invoice')) > 0:
                sheet3 = workbook.add_worksheet('Facturas Abiertas %s' % (cash.get('cashier')))
                sheet3.set_column(0, 0, 5)   # #
                sheet3.set_column(1, 1, 20)  # Número Factura
                sheet3.set_column(2, 2, 25)  # Cliente
                sheet3.set_column(3, 3, 15)  # Fecha Factura
                sheet3.set_column(4, 4, 15)  # Total

                sheet3.merge_range('C4:E4', self.env.user.company_id.name, format1)
                sheet3.merge_range('C5:E5', 'FACTURAS ABIERTAS', format11)
                
                buf_image = io.BytesIO(base64.b64decode(self.env.user.company_id.logo))
                sheet3.insert_image('B1', "any_name.png", {'image_data': buf_image, 'x_scale': 0.2, 'y_scale': 0.2})
                
                sheet3.write(6, 2, 'Desde: %s' % (data.get('date_from')), format22)
                sheet3.write(6, 3, 'Hasta: %s' % (data.get('date_to')), format22)
                sheet3.write(6, 4, 'Cajero: %s' % (cash.get('cashier')), format22)

                pos = 9
                total = 0
                num = 1
                sheet3.write(8, 0, '#', format21)
                sheet3.write(8, 1, 'Número de Factura', format21)
                sheet3.write(8, 2, 'Cliente', format21)
                sheet3.write(8, 3, 'Fecha de Factura', format21)
                sheet3.write(8, 4, 'Total', format21)
                for open_inv in cash.get('open_invoice', []):
                    sheet3.write(pos, 0, num, format22)
                    sheet3.write(pos, 1, open_inv.get('number'), format22)
                    sheet3.write(pos, 2, open_inv.get('partner'), format22)
                    sheet3.write(pos, 3, open_inv.get('date_invoice'), format22)
                    sheet3.write_number(pos, 4, open_inv.get('total'), format3)
                    total += open_inv.get('total', 0)
                    pos += 1
                    num += 1
                
                # Total
                sheet3.write(pos, 3, 'Total:', format24)
                sheet3.write_number(pos, 4, total, format4)



    def get_invoices(self,date_from,date_to,cashier_ids):
        account_payment = self.env['account.payment']
        invoice_model = self.env['account.move']
        
        # Dominio para pagos
        domain_payment = [('payment_type','=','inbound'),('state','in',['posted','paid'])]
        # Dominio para facturas canceladas y abiertas
        domain_invoice = [('move_type','in',['out_invoice','out_refund']),('state','in',['cancel','posted'])]
        
        info_invoice = []
        
        if date_from:
            domain_payment.append(('date','>=',date_from))
            domain_invoice.append(('invoice_date','>=',date_from))
        if date_to:
            domain_payment.append(('date','<=',date_to))
            domain_invoice.append(('invoice_date','<=',date_to))
        
        if cashier_ids:
            domain_payment.append(('create_uid','in',cashier_ids))
            domain_invoice.append(('invoice_user_id','in',cashier_ids))

        obj_payment = account_payment.search(domain_payment)
        invoice_obj = invoice_model.search(domain_invoice)

        journal_array = []
        journal_ids = []
        info_cashier = []
        cancel_invoice = []
        open_invoice = []

        cashiers = self.env['res.users'].browse(cashier_ids)
        for ca in cashiers:
            for payment in obj_payment.filtered(lambda x: x.create_uid.id == ca.id):
                info_invoice.append({
                    'date': self.change_format(str(payment.date)),
                    'create_date': self.change_format2(payment.create_date),
                    'number': payment.name,
                    'total': payment.amount,
                    'journal': payment.journal_id.name,
                    'comercial': payment.create_uid.name,
                    'partner': payment.partner_id.name if payment.partner_id else 'Sin Cliente',
                    'state': self.get_state(payment.state)
                })
                
                # Acumular por diario
                if payment.journal_id.id in journal_ids:
                    journal_array[journal_ids.index(payment.journal_id.id)]['total'] += payment.amount
                else:
                    journal_ids.append(payment.journal_id.id)
                    journal_array.append({
                        'journal': payment.journal_id.name,
                        'total': payment.amount,
                    })

            # Procesar facturas canceladas y abiertas
            for inv in invoice_obj.filtered(lambda x: x.invoice_user_id and x.invoice_user_id.id == ca.id):
                if inv.state == 'cancel':
                    cancel_invoice.append({
                        'date_invoice': self.change_format(str(inv.invoice_date)) if inv.invoice_date else '',
                        'number': inv.name,
                        'total': inv.amount_total,
                        'partner': inv.partner_id.name,
                    })
                if inv.state == 'posted' and inv.payment_state == 'not_paid':
                    open_invoice.append({
                        'date_invoice': self.change_format(str(inv.invoice_date)) if inv.invoice_date else '',
                        'number': inv.name,
                        'total': inv.amount_total,
                        'partner': inv.partner_id.name,
                    })

            info_cashier.append({
                'cashier': ca.name,
                'info': info_invoice if info_invoice else [],
                'journals': journal_array if journal_array else [],
                'cancel_invoice': cancel_invoice if cancel_invoice else [],
                'open_invoice': open_invoice if open_invoice else [],
                'voucher': []
            })
            info_invoice = []
            journal_array = []
            journal_ids = []
            open_invoice = []
            cancel_invoice = []
        return info_cashier

    def get_state(self,state):
        if state == 'draft':
            return 'Borrador'
        elif state == 'posted':
            return 'Publicado'
        elif state == 'paid':
            return 'Pagado'
        elif state == 'reconciled':
            return 'Reconciliado'
        elif state in ('cancel', 'cancelled'):
            return 'Cancelado'
        else:
            return state

    def change_format(self, date_value):
        if not date_value:
            return ''
        try:
            if isinstance(date_value, str):
                return datetime.strptime(date_value, '%Y-%m-%d').strftime('%d/%m/%Y')
            else:
                return date_value.strftime('%d/%m/%Y')
        except:
            return str(date_value)
    
    def change_format2(self, date):
        """
        Convierte una fecha a formato "dd/mm/YYYY HH:MM:SS AM/PM" después de restarle 6 horas.
        """
        if isinstance(date, str):  # Si es string, convertir a datetime
            date = fields.Datetime.from_string(date)

        # Restar 6 horas
        date = date - timedelta(hours=6)

        # Extraer la hora en formato 24h
        time_24_format = date.strftime('%H:%M:%S')
        hour = time_24_format[:2]  # Tomamos solo la hora
        time_12_format = ''

        if int(hour) > 12:  # Convertir a formato de 12h PM
            hour = str(int(hour) - 12)
            if len(hour) == 1:
                hour = '0' + hour  # Asegurar formato 2 dígitos
            time_12_format = time_24_format.replace(time_24_format[:2], hour) + ' PM'

        elif int(hour) < 12:  # AM
            time_12_format = time_24_format + ' AM'

        elif int(hour) == 12:  # Mediodía
            time_12_format = time_24_format + ' M'

        # Formatear la fecha completa con el nuevo formato de hora
        formatted_date = date.strftime('%d/%m/%Y') + ' ' + time_12_format

        return formatted_date