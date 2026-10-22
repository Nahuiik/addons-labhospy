# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime
import io
import base64

class auditReportXlsx(models.AbstractModel):
    _name = 'report.l10n_hn_bank_reconciliation.consoliation_xls'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Bank Reconciliation XLS Report'

    def generate_xlsx_report(self, workbook, data, lines):
        cont = 1
        company_name = self.env.company.name
        account_id=data.get('account_id')
        accounts=self.env['account.account'].search([('id','=',account_id)])
        
        name_account_bank=accounts.name
        name_account = ''
        for account in accounts:
            name_account = account.name+' '
        indexs=1
        sheet = workbook.add_worksheet(name_account)
        value_transit_check=self.generate_ckeck_deposit(workbook,'Transit Check',data.get('id'))
        value_transit_deposit=self.generate_ckeck_deposit(workbook,'Transit Deposit',data.get('id'))
        cont+=1


        format1 = workbook.add_format({'font_size': 14, 'bottom': True, 'right': True, 'left': True, 'top': True, 'align': 'vcenter', 'bold': True})
        format11 = workbook.add_format({'font_size': 15, 'align': 'center', 'right': False, 'left': False, 'bottom': False, 'top': False, 'bold': True})
        format21 = workbook.add_format({'text_wrap': True,'valign':'vcenter','font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#ffffff','bg_color':'#088A08'})
        #format21.set_align('vcenter')
        format22 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': False})
        format22_check = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
        format23 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': False, 'left': False,'bottom': False, 'top': True, 'bold': False})
        formatwhite = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False,'bg_color':'#ffffff'})
        formatwhite_border_top = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': True, 'bold': False,'bg_color':'#ffffff'})
        formatwhite_border_right = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': True,'bottom': False, 'top': False, 'bold': False,'bg_color':'#ffffff'})
        format24 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True})
        format25 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#ffffff','bg_color':'#088A08'})
        format26 = workbook.add_format({'font_size': 10, 'align': 'right', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True})
        format27 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#000000','bg_color':'#ffff00'})
        format28 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True, 'bg_color':'#ffff00'})
        ########### NUMBER FORMAT #######################################
        format3 = workbook.add_format({'align':'right', 'left':True, 'right':True, 'bottom': True, 'top': True, 'font_size': 10,'num_format': '#,##0.00'})
        format4 = workbook.add_format({'font_size': 10, 'align': 'right', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True,'num_format': '#,##0.00','font_color':'#ffffff','bg_color':'#088A08'})
        # format4 = workbook.add_format({'align':'right', 'left':False, 'right':False, 'bottom': False, 'top': False, 'bold':True ,'font_size': 10,'num_format': '#,##0.00'})
        format5 = workbook.add_format({'align':'right', 'left':False, 'right':False, 'bottom': False, 'top': False, 'bold':True ,'font_size': 10,'num_format': '#,##0.00', 'bg_color':'#ffff00'})
        font_size_8 = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8})
        red_mark = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8,
                                        'bg_color': 'red'})
        justify = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 12})
        font_size_8.set_align('center')
        justify.set_align('justify')
        format1.set_align('center')
        red_mark.set_align('center')

        sheet.set_column(0, 0, 3)
        sheet.set_column(1, 1, 17)
        sheet.set_column(2, 2, 11)
        sheet.set_column(3, 3, 19)
        sheet.set_column(4, 4, 2)
        sheet.set_column(5, 5, 17)
        sheet.set_column(6, 6, 5)
        sheet.set_column(7, 7, 12)
        
        sheet_number_s=9
        query = """ SELECT COUNT(reconciliation_id) FROM bank_reconciliation_line WHERE reconciliation_id=%s AND is_reconciled ='f';"""
        self.env.cr.execute(query, (data.get('id'),))
        amount_not_reconciliantion = self.env.cr.dictfetchall()
        amount_count = 0
        for line in amount_not_reconciliantion:
            amount_count = line.get('count') or 0
        rows_number_s = 40 + amount_count
        for sheet_number in range(sheet_number_s):
            for rows_number in range(rows_number_s):
                sheet.write(rows_number, sheet_number, _(''), formatwhite)
                # if sheet_number==1 or sheet_number_s-1==sheet_number:
                #     sheet.write(rows_number, sheet_number, _(''), formatwhite_border_right)
                # if rows_number==0 or rows_number==rows_number_s-1:
                #     sheet.write(rows_number, sheet_number, _(''), formatwhite_border_top)
        
        buf_image = io.BytesIO(base64.b64decode(self.env.company.logo))
        
        sheet.insert_image('B6', "any_name.png", {'image_data': buf_image, 'x_scale': 0.147, 'y_scale': 0.153,})
        sheet.merge_range('B3:H3', company_name, format11)
        sheet.merge_range('B5:H5', _('CONCILIACIÓN BANCARIA ')+name_account_bank, format11)
        sheet.merge_range('C7:G7', _('CUENTA CONTABLE ')+name_account, format11)
        sheet.merge_range('C9:G9', data.get('mes_name')+' 20'+datetime.strptime(self.change_format(data.get('date')), '%d/%m/%Y').strftime('%y'), format11)
        # sheet.merge_range('A4:O4', , format11)
        
        balance_to_bank = self.data_balance_bank(data.get('date'), data.get('account_id'))
        pos = 10
        num = 1
        pos+=2
        sheet.merge_range('C'+str(pos)+':E'+str(pos),_('Saldo Según Banco'),format22)
        sheet.write(pos-1,5,data.get('saldo_final'),format3)
        pos+=2
        sheet.merge_range('C'+str(pos)+':E'+str(pos),_('Saldo Según Libros'),format22)
        sheet.write(pos-1,5,balance_to_bank,format3)
        # pos=18
        pos+=6
        sheet.merge_range('C'+str(pos)+':E'+str(pos),_('Cheques en Transito'),format22)
        sheet.write(pos-1,5,_(''),format22)
        ################################## desgloce de los cheques ################################## 
        pos_1 = self.breakdown_generate(sheet,pos,data.get('id'),format22_check)
        pos=pos_1
        
        
        pos+=2
        sheet.merge_range('C'+str(pos)+':E'+str(pos),_('Cheques en Tránsito'),format22)
        sheet.write(pos-1,5,value_transit_check,format4)
        pos+=2
        sheet.merge_range('C'+str(pos)+':E'+str(pos),_('Depósitos en Tránsito'),format22)
        sheet.write(pos-1,5,value_transit_deposit,format4)
        pos+=2
        sheet.merge_range('C'+str(pos)+':E'+str(pos),_('Subtotal'),format22)
        sheet.write(pos-1,5,value_transit_check-value_transit_deposit,format3)
        sub_total=value_transit_check-value_transit_deposit
        pos+=2
        consolidated_amount = data.get('saldo_final')-sub_total
        sheet.merge_range('C'+str(pos)+':E'+str(pos),_('Saldo Conciliado'),format22)
        sheet.write(pos-1,5,consolidated_amount,format3)
        pos+=2
        sheet.merge_range('C'+str(pos)+':E'+str(pos),_('Diferencia'),format22)
        sheet.write(pos-1,5,balance_to_bank-consolidated_amount,format3)
        pos+=8
        sheet.merge_range('B'+str(pos)+':C'+str(pos),_('Elaborado por'),format23)
        sheet.merge_range('E'+str(pos)+':G'+str(pos),_('Contador General'),format23)
        pos+=2
        # sheet.write(pos-1,5,value_transit_check+value_transit_deposit,format25)
    def generate_ckeck_deposit(self, workbook, name, id):
        name_map = {
            'Transit Check': _('Cheques en Tránsito'),
            'Transit Deposit': _('Depósitos en Tránsito'),
        }
        sheet_name = name_map.get(name, _(name))
        sheet = workbook.add_worksheet(sheet_name)
        format21 = workbook.add_format({'text_wrap': True,'valign':'vcenter','font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#ffffff','bg_color':'#088A08'})
        format25 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#ffffff','bg_color':'#088A08'})
        format22 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
        value=0
        conciliacion= self.env['bank.reconciliation'].search([('id','=',id)])
        if name == 'Transit Deposit':
            pos=2
            sheet.set_column(0, 0, 5)
            sheet.set_column(1, 1, 9)
            sheet.set_column(2, 2, 18)
            sheet.set_column(3, 3, 50)
            sheet.set_column(4, 4, 32)
            sheet.set_column(5, 5, 12)
            sheet.write(pos, 0, _('No.'), format21)
            sheet.write(pos, 1, _('Fecha'), format21)
            sheet.write(pos, 2, _('Número Depósito'), format21)
            sheet.write(pos, 3, _('Referencia'), format21)
            sheet.write(pos, 4, _('Motivo de pago'), format21)
            sheet.write(pos, 5, _('Valor'), format21)
            pos+=1
            num=1
            for line in conciliacion.reconciliation_line:
                if not line.is_reconciled:
                    if line.debit>0:
                        value+=line.debit
                        sheet.write(pos,0,num,format25)
                        sheet.write(pos, 1, self.change_format(str(line.date)),format22)
                        sheet.write(pos, 2, line.move_id.name,format22)
                        sheet.write(pos, 3, line.name,format22)
                        sheet.write(pos, 5, line.debit,format22)
                        pos+=1
                        num+=1
            pos+=1
            sheet.write(pos, 3, _('Total Depósitos en Tránsito'), format22)
            sheet.write(pos, 5, value,format22)
        elif name == 'Transit Check':
            pos=2
            sheet.set_column(0, 0, 5)
            sheet.set_column(1, 1, 9)
            sheet.set_column(2, 2, 18)
            sheet.set_column(3, 3, 27)
            sheet.set_column(4, 4, 32)
            sheet.write(2, 0, _('No.'), format21)
            sheet.write(2, 1, _('Fecha'), format21)
            sheet.write(2, 2, _('Número Cheque'), format21)
            sheet.write(2, 3, _('Referencia'), format21)
            sheet.write(2, 4, _('Valor'), format21)
            pos+=1
            num=1
            for line in conciliacion.reconciliation_line:
                if not line.is_reconciled:
                    if line.credit>0:
                        value+=line.credit
                        sheet.write(pos,0,num,format25)
                        sheet.write(pos, 1, self.change_format(str(line.date)),format22)
                        sheet.write(pos, 2, line.move_id.name,format22)
                        sheet.write(pos, 3, line.name,format22)
                        sheet.write(pos, 4, line.credit,format22)
                        pos+=1
                        num+=1
            pos+=1
            sheet.write(pos, 3, _('Total Cheques en Tránsito'), format22)
            sheet.write(pos, 4, value,format22)
        return value
    def data_balance_bank(self, date_end, account_id):
        """Calcula el saldo según libros hasta date_end para la cuenta account_id."""
        if not account_id:
            return 0.0
        self.env.cr.execute("""
            SELECT COALESCE(SUM(debit - credit), 0) as balance
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            WHERE aml.account_id = %s
              AND am.date <= %s
              AND am.state = 'posted'
        """, (account_id, date_end))
        row = self.env.cr.fetchone()
        return row[0] if row else 0.0
    def breakdown_generate(self,sheet,pos,id,format22):
        value=0
        conciliacion= self.env['bank.reconciliation'].search([('id','=',id)])
        for line in conciliacion.reconciliation_line:
            if not line.is_reconciled:
                if line.credit>0:
                    sheet.write(pos, 2, line.move_id.name,format22)
                    sheet.write(pos, 3, line.name,format22)
                    sheet.write(pos, 5, line.credit,format22)
                    pos+=1
        return pos
    def change_format(self,date):
        if date:
            return datetime.strptime(date, '%Y-%m-%d').strftime('%d/%m/%Y')
        else:
            return date