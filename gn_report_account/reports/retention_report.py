# -*- coding: utf-8 -*-
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
from datetime import datetime,timedelta
import calendar


class RetentionReportXls(models.AbstractModel):
    _name = 'report.gn_report_account.retention_report_xls.xlsx'
    _description = 'Retention Report XLS'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, lines):
        info = self.get_data(data.get('start_date'),data.get('end_date'),data.get('report_type'))
        sheet = workbook.add_worksheet(_('Retention'))
        format1 = workbook.add_format(
            {'font_size': 14, 'bottom': True, 'right': True, 'left': True, 'top': True, 'align': 'center',
                'bold': True})
        format4 = workbook.add_format({'align':'center', 'left':True, 'right':True, 'bottom': True, 'top': True, 'font_size': 10,'num_format': '#,##0.00', 'bold': True, 'bg_color':'#dbeb34'})
        format21 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#ffffff','bg_color':'#000000'})
        format23 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True, 'text_wrap': True})
        format22 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': False, 'text_wrap': True})
        format24 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': False, 'text_wrap': True, 'num_format': '#,##0.00'})
       
        #1% Retencion
        # if data.get('report_type') == '1_per':
        sheet.set_column(0, 0, 6)
        sheet.set_column(1, 1, 18)
        sheet.set_column(2, 2, 18)
        sheet.set_column(3, 3, 18)
        sheet.set_column(4, 4, 18)
        sheet.set_column(5, 5, 28)
        sheet.set_column(6, 6, 17)
        sheet.set_column(7, 7, 30)
        sheet.set_column(8, 8, 15)
        sheet.set_column(9, 9, 15)
        sheet.set_column(10, 10, 15)
        sheet.set_column(11, 11, 15)
        sheet.set_column(12, 12, 15)
        sheet.set_column(13, 13, 15)
        sheet.set_column(14, 14, 15)
        sheet.set_column(15, 15, 15)
        sheet.set_column(16, 16, 15)
            
        sheet.merge_range('A5:Q5', self.env.user.company_id.name, format1)
        if data.get('start_date'):
            sheet.merge_range('A7:B7', _("Fecha Inicial: "+datetime.strptime(data.get('start_date')+" 00:00:00",DEFAULT_SERVER_DATETIME_FORMAT).strftime('%d-%m-%Y')),format23)
        if data.get('end_date'):
            sheet.merge_range('C7:D7', _("Fecha Fin: "+datetime.strptime(data.get('end_date')+" 00:00:00",DEFAULT_SERVER_DATETIME_FORMAT).strftime('%d-%m-%Y')),format23)
            # sheet.write(6, 3, _("Fecha Fin: "+datetime.strptime(data.get('end_date')+" 00:00:00",DEFAULT_SERVER_DATETIME_FORMAT).strftime('%d-%m-%Y')),format23)
        if data.get('report_type') == '1_per':
            sheet.write(6, 5, _('Retención del 1% '),format23)
        elif data.get('report_type') == '12_per':
            sheet.write(6, 5, _('Retención del 12.5% '),format23)
        elif data.get('report_type') == '15_per':
            sheet.write(6, 5, _('Retención del 15% '),format23)
        sheet.merge_range('G7:H7', _("Fecha de impresión: "+datetime.today().replace(microsecond=0).strftime('%d-%m-%Y %H:%M:%S')),format23)

        # sheet.merge_range('A9:B9', _("Nombre: Retencion 1%"),format23)
        sheet.write(9, 0, _('No.'), format21)
        sheet.write(9, 1, _('Fecha Pago.'), format21)
        sheet.write(9, 2, _('Numero de pago'), format21)
        sheet.write(9, 3, _('Tipo de pago'), format21)
        sheet.write(9, 4, _('Secuencia'), format21)
        sheet.write(9, 5, _('Nombre Proveedor'), format21)
        sheet.write(9, 6, _('RTN'), format21)
        sheet.write(9, 7, _('Diario'), format21)
        sheet.write(9, 8, _('Factura'), format21)
        sheet.write(9, 9, _('Fecha Factura'), format21)
        sheet.write(9, 10, _('Referencia Factura'), format21)
        sheet.write(9, 11, _('Estado Factura'), format21)
        sheet.write(9, 12, _('Base'), format21)
        sheet.write(9, 13, _('Retención 1%'), format21)
        sheet.write(9, 14, _('Retención 12.5%'), format21)
        sheet.write(9, 15, _('Retención 15%'), format21)
        sheet.write(9, 16, _('Total Retención'), format21)
        num=0
        pos=10
        total_base = 0
        total_retention = 0
        retentions_1=0.00
        retentions_12_5=0.00
        retentions_15=0.00
        for invoice in info:    
            total_base += invoice.get('base_retentions')
            retentions_1+=invoice.get('retentions_1')
            retentions_12_5+=invoice.get('retentions_12_5')
            retentions_15+=invoice.get('retentions_15')
            total_ret = invoice.get('retentions_1') + invoice.get('retentions_12_5') + invoice.get('retentions_15')
            total_retention += total_ret        
            sheet.write(pos, 0, num, format21)
            sheet.write(pos, 1, invoice.get('date_payment'), format22)
            sheet.write(pos, 2, invoice.get('name_move_payment'), format22)
            sheet.write(pos, 3, invoice.get('type_payment'), format22)
            sheet.write(pos, 4, invoice.get('sequence_ret'), format22)
            sheet.write(pos, 5, invoice.get('name_partner'), format22)
            sheet.write(pos, 6, invoice.get('rtn_partner'), format22)
            sheet.write(pos, 7, invoice.get('journal'), format22)
            sheet.write(pos, 8, invoice.get('invoice_name'), format22)
            sheet.write(pos, 9, invoice.get('invoice_date'), format22)
            sheet.write(pos, 10, invoice.get('invoice_ref'), format22)
            sheet.write(pos, 11, invoice.get('invoice_state'), format22)
            sheet.write(pos, 12, invoice.get('base_retentions'), format24)
            sheet.write(pos, 13, invoice.get('retentions_1'), format24)
            sheet.write(pos, 14, invoice.get('retentions_12_5'), format24)
            sheet.write(pos, 15, invoice.get('retentions_15'), format24)
            sheet.write(pos, 16, total_ret, format24)
            num += 1
            pos += 1
        sheet.write(pos, 11, _('Total General'), format4)
        sheet.write_number(pos, 12, total_base, format4)
        sheet.write_number(pos, 13, retentions_1, format4)
        sheet.write_number(pos, 14, retentions_12_5, format4)
        sheet.write_number(pos, 15, retentions_15, format4)
        sheet.write_number(pos, 16, total_retention, format4)
    def get_data(self,start_date,end_date,report_type):
        info=[]
        query="""SELECT
                    pay.payment_move_type,
                    pay.retention_sequence_id AS sequence_ret,
                    pay.payment_move_type AS type_payment,
                    pay.create_date AS date_payment,
                    pay_line.amount_total AS base_retentions,
                    pay_line.supplier_invoice_number AS number_invoice,
                    pay_line.amount_retention_1 AS retentions_1,
                    pay_line.amount_retention_12_5 AS retentions_12_5,
                    pay_line.amount_retention_15 AS retentions_15,
                    partners.name AS name_partner,
                    partners.rtn AS rtn_partner,
                    moves.name AS name_move_payment,
                    moves.ref AS reference,
                    (SELECT journals.name FROM account_journal AS journals
                        WHERE moves.journal_id = journals.id
                    ) AS journal,
                    invoice.name AS invoice_name,
                    invoice.date AS invoice_date,
                    invoice.ref AS invoice_ref,
                    invoice.state AS invoice_state,
                    invoice.supplier_invoice_number AS num_invoice_supplier
                FROM account_payment AS pay
                INNER JOIN payment_invoice_line AS pay_line
                ON pay.id = pay_line.payment_id
                INNER JOIN res_partner AS partners
                ON partners.id = pay.partner_id
                INNER JOIN account_move AS moves
                ON moves.id = pay.move_id
                INNER JOIN account_move AS invoice
                ON invoice.id = pay_line.invoice_id
                WHERE """
        # print('===start_date====>>',start_date)
        if start_date:
            date_payments = "moves.date >= '" + start_date +"' AND "
            query += date_payments
        if end_date:
            date_payments = "moves.date <= '" + end_date +"' AND "
            query += date_payments
        if report_type == '1_per':
            query += ' pay_line.amount_retention_1 IS NOT NULL AND'
        elif report_type == '12_per':
            query += ' pay_line.amount_retention_12_5 IS NOT NULL AND pay_line.amount_retention_12_5 > 0 AND'
        elif report_type == '15_per':
            query += ' pay_line.amount_retention_15 IS NOT NULL AND pay_line.amount_retention_15 > 0 AND'
        query+= """ pay.apply_retentions='t' AND pay.partner_type='supplier' ; """
        self.env.cr.execute(query)
        payments_ids = self.env.cr.dictfetchall()
        for payment in payments_ids:
            info.append({
                'date_payment': self.change_format(payment.get('date_payment')),
                'name_move_payment':payment.get('name_move_payment'),
                'type_payment':payment.get('type_payment'),
                'sequence_ret':payment.get('sequence_ret'),
                'name_partner':payment.get('name_partner'),
                'rtn_partner':payment.get('rtn_partner'),
                'journal':payment.get('journal'),
                'invoice_name':payment.get('invoice_name'),
                'invoice_date':datetime.strptime(str(payment.get('invoice_date')), '%Y-%m-%d').strftime('%d/%m/%Y'),
                'invoice_ref':payment.get('invoice_ref'),
                'invoice_state':payment.get('invoice_state'),
                'base_retentions':payment.get('base_retentions') or 0.00,
                'retentions_1':payment.get('retentions_1') or 0.00,
                'retentions_12_5':payment.get('retentions_12_5') or 0.00,
                'retentions_15':payment.get('retentions_15') or 0.00,                  
            })
        list2 = sorted(info, key=lambda inv: inv.get('date_payment'))
        return list2
    def change_format(self,date):
        if date:
            date_format = date.strftime('%Y-%m-%d')
            date_string = datetime.strptime(str(date_format), '%Y-%m-%d').strftime('%d/%m/%Y')
            return date_string
        else:
            return date
