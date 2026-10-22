# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from functools import reduce
import datetime 
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT,DEFAULT_SERVER_DATE_FORMAT
from datetime import datetime
import io
import base64
from dateutil.relativedelta import relativedelta

class StateResultMonthlyXLSX(models.AbstractModel):
    _name = 'report.gn_report_account.state_result_monthly_report_xls.xlsx'
    _description = 'State Result Monthly Report XLS'
    _inherit = 'report.report_xlsx.abstract'
    
    def generate_xlsx_report(self, workbook, data, lines):
        company_name = self.env.user.company_id.name
        sheet = workbook.add_worksheet(_('Supplier Account State'))
        date_header_month = self.date_header_month(data.get('start_date'),data.get('end_date'))
        info, month = self.get_data(data.get('start_date'),data.get('end_date'))
        
        format1 = workbook.add_format({'font_size': 14, 'bottom': True, 'right': True, 'left': True, 'top': True, 'align': 'vcenter', 'bold': True})
        format11 = workbook.add_format({'font_size': 15, 'align': 'center', 'right': False, 'left': False, 'bottom': False, 'top': False, 'bold': True})
        format21 = workbook.add_format({'text_wrap':True,'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#000000','bg_color':'#FFFFFF'})
        format22 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
        format22a = workbook.add_format({'font_size': 12, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False, 'bold': True, 'bg_color':'#7EB1EF', 'num_format': 'L #,##0.00'})
        format22b = workbook.add_format({'font_size': 12, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False, 'bold': True, 'bg_color':'#FFC2B5', 'num_format': 'L #,##0.00'})
        format22c = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': True, 'top': True, 'bold': False})
        format24 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True})
        format25 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#ffffff','bg_color':'#088A08'})
        format26_pos = workbook.add_format({'font_size': 12, 'align': 'left', 'right': False, 'left': False,'bottom': True, 'top': True, 'bold': True, 'font_color':'#7EB1EF', 'num_format': 'L #,##0.00'})
        format26_neg = workbook.add_format({'font_size': 12, 'align': 'left', 'right': False, 'left': False,'bottom': True, 'top': True, 'bold': True, 'font_color':'#FFC2B5', 'num_format': 'L #,##0.00'})
        ########### NUMBER FORMAT #######################################
        format3 = workbook.add_format({'align':'right', 'left':False, 'right':False, 'bottom': False, 'top': False, 'font_size': 10,'num_format': 'L #,##0.00'})
        format4 = workbook.add_format({'align':'right', 'left':False, 'right':False, 'bottom': False, 'top': False, 'font_size': 10,'num_format': '0.00%'})
        font_size_8 = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8})
        red_mark = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8,
                                        'bg_color': 'red'})
        justify = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 12})
        font_size_8.set_align('center')
        justify.set_align('justify')
        format1.set_align('center')
        red_mark.set_align('center')
        format22c.set_underline(2)
        # format26_neg.set_underline(2)

        sheet.set_column(0, 0, 12)
        sheet.set_column(1, 1, 50)
        sheet.set_column(2, 2, 19)
        sheet.set_row(7,26)
        sheet.merge_range('A3:I3', company_name, format11)
        sheet.merge_range('A4:I4', _('ESTADO DE RESULTADO MENSUALIZADO DE %s')%(date_header_month), format11)

        sheet.merge_range('A7:B7', _('Start Date: %s')%(self.change_format(data.get('start_date'))), format24)
        sheet.merge_range('C7:D7', _('End Date: %s')%(self.change_format(data.get('end_date'))), format24)
        sheet.merge_range('E7:F7', _('Print Date: %s')%(datetime.today().strftime('%Y-%m-%d')), format24)

        pos = 8
        num = 1
        sheet.write(pos, 0, _('Cuenta'), format21)
        sheet.write(pos, 1, _('Nombre'), format21)
        sheet.write(pos, 2, _('Saldo'), format21)
        rows = 4
        for line in month:
            string_date= self.generate_date_header(line.get('month'), line.get('year'))
            sheet.write(pos, rows, string_date, format21)
            rows+=2
        group_id = []
        group_dicc =[]
        header_accounts_4 = header_accounts_5 = header_accounts_6 = header_accounts_7 = True
        pos+=1
        balance=0
        position_accounts = []
        for inv in info:
            if inv.get('code')[0:1]=='4':
                pos,group_id,group_dicc,header_accounts_4,position_accounts = self.generate_account(pos,inv,group_id,group_dicc,header_accounts_4,sheet,format22,format3,-1,position_accounts)
            if inv.get('code')[0:1]=='5':
                pos,group_id,group_dicc,header_accounts_5,position_accounts = self.generate_account(pos,inv,group_id,group_dicc,header_accounts_5,sheet,format22,format3,1,position_accounts)
            if inv.get('code')[0:1]=='6':
                pos,group_id,group_dicc,header_accounts_6,position_accounts = self.generate_account(pos,inv,group_id,group_dicc,header_accounts_6,sheet,format22,format3,1,position_accounts)
            if inv.get('code')[0:1]=='7':
                pos,group_id,group_dicc,header_accounts_7,position_accounts = self.generate_account(pos,inv,group_id,group_dicc,header_accounts_7,sheet,format22,format3,1,position_accounts)
        totals_account_4 = totals_account_5 = totals_account_6 = totals_account_7= 0.00
        totals_account_4_pos =  totals_account_5_pos =  totals_account_6_pos =  totals_account_7_pos = 0 
        totals_account_4_bol = totals_account_5_bol =  totals_account_6_bol =  totals_account_7_bol = True 
        totals_account_4_dicc = [] 
        totals_account_5_dicc = []
        totals_account_6_dicc = []
        totals_account_7_dicc = []
        len_dic=len(month)
        for dicc in group_dicc:
            if dicc.get('code')[0:1]=='4':
                totals_account_4_bol,totals_account_4_pos,totals_account_4_dicc,totals_account_4 = self.generate_account_subtotal(dicc,sheet,format22a,len_dic, totals_account_4_bol,totals_account_4_pos,totals_account_4_dicc,totals_account_4)
            if dicc.get('code')[0:1]=='5':
                totals_account_5_bol,totals_account_5_pos,totals_account_5_dicc,totals_account_5 = self.generate_account_subtotal(dicc,sheet,format22a,len_dic, totals_account_5_bol,totals_account_5_pos,totals_account_5_dicc,totals_account_5)
            if dicc.get('code')[0:1]=='6':
                totals_account_6_bol,totals_account_6_pos,totals_account_6_dicc,totals_account_6 = self.generate_account_subtotal(dicc,sheet,format22a,len_dic, totals_account_6_bol,totals_account_6_pos,totals_account_6_dicc,totals_account_6)
            if dicc.get('code')[0:1]=='7':
                totals_account_7_bol,totals_account_7_pos,totals_account_7_dicc,totals_account_7 = self.generate_account_subtotal(dicc,sheet,format22a,len_dic, totals_account_7_bol,totals_account_7_pos,totals_account_7_dicc,totals_account_7)
        if not totals_account_4_bol:
            totals_account_4_pos,totals_account_4,totals_account_4_dicc = self.generate_account_total(sheet,format22b ,totals_account_4_pos,totals_account_4,totals_account_4_dicc)
        if not totals_account_5_bol:
            totals_account_5_pos,totals_account_5,totals_account_5_dicc = self.generate_account_total(sheet,format22b ,totals_account_5_pos,totals_account_5,totals_account_5_dicc)
        if not totals_account_6_bol:
            totals_account_6_pos,totals_account_6,totals_account_6_dicc = self.generate_account_total(sheet,format22b ,totals_account_6_pos,totals_account_6,totals_account_6_dicc)
        if not totals_account_7_bol:
            totals_account_7_pos,totals_account_7,totals_account_7_dicc = self.generate_account_total(sheet,format22b ,totals_account_7_pos,totals_account_7,totals_account_7_dicc)
        pos+=1
        totals_b_n = totals_account_4 - totals_account_5 - totals_account_6 - totals_account_7
        line_ben = 2*(len_dic) +4
        for line in range(line_ben):
            sheet.write(pos,line, _(''),format22c)
        sheet.write(pos,1, _('Beneficio Neto'),format22c)
        if totals_b_n>=0:
            sheet.write(pos, 2, totals_b_n, format26_pos)
        else:
            sheet.write(pos, 2, totals_b_n, format26_neg)
        rows = 4
        for index in range(len_dic):
            if totals_account_4_dicc and totals_account_5_dicc and totals_account_6_dicc and totals_account_7_dicc:
                totals_line_b_n = totals_account_4_dicc[index].get('balance') - totals_account_5_dicc[index].get('balance') - totals_account_6_dicc[index].get('balance') - totals_account_7_dicc[index].get('balance')
                if totals_line_b_n>=0:
                    sheet.write(pos, rows, totals_line_b_n, format26_pos)
                else:
                    sheet.write(pos, rows, totals_line_b_n, format26_neg)
                rows +=2
        

        for position in position_accounts:
            if position.get('code')=='4':
                sheet.write_array_formula('D'+str(position.get('positions')+1), '=(C'+str(position.get('positions')+1)+'/C'+str(totals_account_4_pos+1)+')',format4)
            elif position.get('code')=='5':
                sheet.write_array_formula('D'+str(position.get('positions')+1), '=(C'+str(position.get('positions')+1)+'/C'+str(totals_account_5_pos+1)+')',format4)
            elif position.get('code')=='6':
                sheet.write_array_formula('D'+str(position.get('positions')+1), '=(C'+str(position.get('positions')+1)+'/C'+str(totals_account_6_pos+1)+')',format4)
            elif position.get('code')=='7':
                sheet.write_array_formula('D'+str(position.get('positions')+1), '=(C'+str(position.get('positions')+1)+'/C'+str(totals_account_7_pos+1)+')',format4)
    def get_data(self, start_date, end_date):
        info = []
        domain=[]
        group_ids = []
        value_dicc=[]
        accounts_code =[]
        domain.append(('state','=','posted'))
        if start_date:
            domain.append(('date','>=',start_date))
        if end_date:
            domain.append(('date','<=',end_date))
        month = self._get_date(start_date, end_date)
        account = self.env['account.move'].search(domain)
        index=0###
        account = sorted(account, key=lambda k: k.date, reverse=False)
        for move in account:
            year_start = int(datetime.strptime(str(move.date), '%Y-%m-%d').strftime('%Y'))
            month_start = int(datetime.strptime(str(move.date), '%Y-%m-%d').strftime('%m'))
            for line in move.line_ids:
                if line.account_id:
                    if line.account_id.code:
                        if line.account_id.code[0:1]=='4'  or line.account_id.code[0:1]=='5' or line.account_id.code[0:1]=='6' or line.account_id.code[0:1]=='7':
                            if line.account_id.group_id:
                                if not line.account_id.group_id in group_ids:
                                    group_ids.append(line.account_id.group_id)
                            if line.account_id.code in accounts_code:
                                balance = line.debit - line.credit 
                                info[accounts_code.index(line.account_id.code)]['balance'] += balance
                                values = info[accounts_code.index(line.account_id.code)]['value']
                                for value in values:
                                    if value.get('year') == year_start and value.get('month') == month_start:
                                        value['value'] += balance
                            else:
                                for month_in in month:
                                    value_dicc.append({
                                        'year':month_in.get('year'),
                                        'month':month_in.get('month'),
                                        'value':month_in.get('value'),
                                    })
                                accounts_code.append(line.account_id.code)
                                balance = line.debit - line.credit
                                info.append({
                                    'code': line.account_id.code,
                                    'name': line.account_id.name,
                                    'balance': balance,
                                    'value': value_dicc,
                                    'group_id_name': line.account_id.group_id.name,
                                    'group_ids': line.account_id.group_id,
                                })
                                value_dicc = []
                                values = info[accounts_code.index(line.account_id.code)]['value']
                                for value in values:
                                    if value.get('year') == year_start and value.get('month') == month_start:
                                        value['value'] = balance
                            index+=1###
        info = sorted(info, key=lambda k: k.get('code'),reverse=False)
        group_ids = sorted(group_ids, key=lambda k: k.code_prefix_start,reverse=False)
        # print('=====len===',len(info))
        return info,month
    def change_format(self,date):
        if date:
            return datetime.strptime(date, '%Y-%m-%d').strftime('%d/%m/%Y')
        else: 
            return date
    def _get_date(self,date_start, date_end):
        mount=[]
        date_int=0
        if date_start and date_end:
            date_end_2 = datetime.strptime(date_end, '%Y-%m-%d')
            date_start_2 = datetime.strptime(date_start, '%Y-%m-%d')
            delta = relativedelta(date_end_2,date_start_2)
            if delta:
                month_day=0
                if delta.days>0:
                    month_day=1
                date_int = (delta.years)*12 + delta.months + month_day
            date_end_2 = datetime.strptime(date_end, '%Y-%m-%d').strftime('%m')
            months = self.month_date_start_and_end(date_int,date_start, date_end)
        return months
    def month_date_start_and_end(self,int_month,date_start, date_end):
        month=[]
        month_start = int(datetime.strptime(date_start, '%Y-%m-%d').strftime('%m'))
        year_start = int(datetime.strptime(date_start, '%Y-%m-%d').strftime('%Y'))
        print('===month_start===',month_start)
        for index in range(int_month):
            if month_start>12:
                month_start=1
                year_start+=1
            month.append({
                'year':year_start,
                'month':month_start,
                'value':0,
            })
            month_start+=1
        return month

    def generate_date_header(self,month,year):
        string_date=''
        if month and year:
            if month==1:
                string_date = 'ENE. ' + str(year)
            elif month==2:
                string_date = 'FEB. ' + str(year)
            elif month==3:
                string_date = 'MAR. ' + str(year)
            elif month==4:
                string_date = 'ABR. ' + str(year)
            elif month==5:
                string_date = 'MAY. ' + str(year)
            elif month==6:
                string_date = 'JUN. ' + str(year)
            elif month==7:
                string_date = 'JUL. ' + str(year)
            elif month==8:
                string_date = 'AGOS. ' + str(year)
            elif month==9:
                string_date = 'SEP. ' + str(year)
            elif month==10:
                string_date = 'OCT. ' + str(year)
            elif month==11:
                string_date = 'NOV. ' + str(year)
            elif month==12:
                string_date = 'DIC. ' + str(year)
        return string_date

    def date_header_month(self,start_date,end_date):
        date_string=''
        month_start = int(datetime.strptime(start_date, '%Y-%m-%d').strftime('%m'))
        month_end = int(datetime.strptime(end_date, '%Y-%m-%d').strftime('%m'))
        year_start = int(datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y'))
        year_end = int(datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y'))
        if year_start == year_end:
            month_start_string = self.generate_date_header_2(month_start)
            month_end_string = self.generate_date_header_2(month_end)
            date_string= ' '+ month_start_string +'- '+ month_end_string + str(year_start)
        else:
            month_start_string = self.generate_date_header_2(month_start)
            month_end_string = self.generate_date_header_2(month_end)
            date_string= ' '+ month_start_string + str(year_start)+' - '+ month_end_string + str(year_end)
        return date_string

    def generate_date_header_2(self,month):
        string_date=''
        if month:
            if month==1:
                string_date = 'ENE. '
            elif month==2:
                string_date = 'FEB. '
            elif month==3:
                string_date = 'MAR. '
            elif month==4:
                string_date = 'ABR. '
            elif month==5:
                string_date = 'MAY. '
            elif month==6:
                string_date = 'JUN. '
            elif month==7:
                string_date = 'JUL. '
            elif month==8:
                string_date = 'AGOS. '
            elif month==9:
                string_date = 'SEP. '
            elif month==10:
                string_date = 'OCT. '
            elif month==11:
                string_date = 'NOV. '
            elif month==12:
                string_date = 'DIC. '
        return string_date

    def generate_account(self,pos,inv,group_id,group_dicc,header_accounts,sheet,format22,format3,num,position_accounts):
        if inv.get('group_ids') in group_id:
            group_dicc[group_id.index(inv.get('group_ids'))]['balance'] += (inv.get('balance')*num)
            values = group_dicc[group_id.index(inv.get('group_ids'))]['values']
            index = 0
            for val in inv.get('value'):
                values[index]['balance'] += (val.get('value')*num)
                index+=1
        else:
            if header_accounts:
                pos+=1
                if inv.get('group_ids').parent_id:
                    if inv.get('group_ids').parent_id.parent_id:
                        if inv.get('group_ids').parent_id.parent_id.parent_id:
                            sheet.write(pos,0, inv.get('group_ids').parent_id.parent_id.parent_id.code_prefix_start,format22)
                            sheet.write(pos,1, inv.get('group_ids').parent_id.parent_id.parent_id.name,format22)
                            pos+=1
                        sheet.write(pos,0, inv.get('group_ids').parent_id.parent_id.code_prefix_start,format22)
                        sheet.write(pos,1, inv.get('group_ids').parent_id.parent_id.name,format22)
                        pos+=1
                    sheet.write(pos,0, inv.get('group_ids').parent_id.code_prefix_start,format22)
                    sheet.write(pos,1, inv.get('group_ids').parent_id.name,format22)
                    pos+=1
                header_accounts = False
            sheet.write(pos,0, inv.get('group_ids').code_prefix_start,format22)
            sheet.write(pos,1, inv.get('group_id_name'),format22)
            group_id.append(inv.get('group_ids'))
            value=[]
            for val in inv.get('value'):
                value.append({
                    'balance': val.get('value')*num,
                })
            group_dicc.append({
                'position': pos,
                'code': inv.get('group_ids').code_prefix_start,
                'balance':inv.get('balance')*num,
                'values': value
            })
            pos+=1
        sheet.write(pos,0, inv.get('code'),format22)
        sheet.write(pos,1, inv.get('name'),format22)
        sheet.write(pos,2, inv.get('balance')*num,format3)
        position_accounts.append({'positions':pos,'code':inv.get('code')[0:1]})
        rows=4
        index=0
        for val in inv.get('value'):
            sheet.set_column(rows, rows, 19)
            sheet.set_column(rows+1, rows+1, 8)
            sheet.write(pos, rows, val.get('value')*num, format3)
            rows+=2
        pos+=1
        return pos,group_id,group_dicc,header_accounts,position_accounts
    def generate_account_subtotal(self, dicc,sheet,format22a,len_dic ,totals_account_bol,totals_account_pos,totals_account_dicc,totals_account):
        if totals_account_bol:
            totals_account_pos = dicc.get('position') - 1
            for index in range(len_dic):
                totals_account_dicc.append({
                    'balance':0
                })
        totals_account+=dicc.get('balance')
        totals_account_bol=False
        sheet.write(dicc.get('position'), 2, dicc.get('balance'), format22a)
        rows=4
        index=0
        for val in dicc.get('values'):
            sheet.write(dicc.get('position'), rows, val.get('balance'), format22a)
            totals_account_dicc[index]['balance']+= val.get('balance')
            index+=1
            rows+=2
        return totals_account_bol,totals_account_pos,totals_account_dicc,totals_account
    def generate_account_total(self,sheet,format22b ,totals_account_pos,totals_account,totals_account_dicc):
        sheet.write(totals_account_pos, 2, totals_account, format22b)
        rows=4
        for val in totals_account_dicc:
            sheet.write(totals_account_pos, rows, val.get('balance'), format22b)
            rows+=2
        return totals_account_pos,totals_account,totals_account_dicc
