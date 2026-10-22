# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime
import io
import base64

class advanceNotAppliedtXlsx(models.AbstractModel):
    _name = 'report.gn_report_account.advance_not_applied_xls.xlsx'
    _description = 'Advances Not Applied XLS'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, lines):
        cont = 1
        company_name = self.env.user.company_id.name
        sheet = workbook.add_worksheet(_('Not Applied'))
        info = self.get_data(data.get('start_date'),data.get('end_date'))

        cont+=1
        format1 = workbook.add_format({'font_size': 14, 'bottom': True, 'right': True, 'left': True, 'top': True, 'align': 'vcenter', 'bold': True})
        format11 = workbook.add_format({'font_size': 15, 'align': 'center', 'right': False, 'left': False, 'bottom': False, 'top': False, 'bold': True})
        format21 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#ffffff','bg_color':'#088A08'})
        format22 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
        format23 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True})
        format24 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
        format25 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#ffffff','bg_color':'#088A08'})
        format26 = workbook.add_format({'font_size': 10, 'align': 'right', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True})
        format27 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True, 'font_color':'#000000','bg_color':'#ffff00'})
        format28 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True, 'bg_color':'#ffff00'})
        ########### NUMBER FORMAT #######################################
        format3 = workbook.add_format({'align':'right', 'left':False, 'right':False, 'bottom': False, 'top': False, 'font_size': 10,'num_format': '#,##0.00'})
        format4 = workbook.add_format({'align':'right', 'left':False, 'right':False, 'bottom': False, 'top': False, 'bold':True ,'font_size': 10,'num_format': '#,##0.00'})
        format5 = workbook.add_format({'align':'right', 'left':False, 'right':False, 'bottom': False, 'top': False, 'bold':True ,'font_size': 10,'num_format': '#,##0.00', 'bg_color':'#ffff00'})
        font_size_8 = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8})
        red_mark = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8,
                                        'bg_color': 'red'})
        justify = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 12})
        font_size_8.set_align('center')
        justify.set_align('justify')
        format1.set_align('center')
        red_mark.set_align('center')

        sheet.set_column(0, 0, 5)
        sheet.set_column(1, 1, 15)
        sheet.set_column(2, 2, 35)
        sheet.set_column(3, 3, 35)
        sheet.set_column(4, 4, 15)
        sheet.set_column(5, 5, 15)
        sheet.set_column(6, 6, 15)
        sheet.set_column(7, 7, 15)
        sheet.set_column(8, 8, 20)
        sheet.set_column(9, 9, 35)
        sheet.set_column(10, 10, 28)

        sheet.merge_range('A3:G3', company_name, format11)
        sheet.merge_range('A4:G4', _('ADVANCE NOT APPLIED'), format11)

        pos = 4
        num = 1
        total = 0
        sheet.write(4, 0, _('No.'), format21)
        sheet.write(4, 1, _('Deposit Date'), format21)
        sheet.write(4, 2, _('Depositor Name'), format21)
        sheet.write(4, 3, _('Patient Name'), format21)
        sheet.write(4, 4, _('Receipt N°'), format21)
        sheet.write(4, 5, _('Receipt Total'), format21)
        sheet.write(4, 6, _('Amount Applied'), format21)
        sheet.write(4, 7, _('Balance'), format21)
        sheet.write(4, 8, _('Invoice'), format21)
        sheet.write(4, 9, _('Accounting Accounts'), format21)
        sheet.write(4, 10, _('Creation User'), format21)
        pos+=1
        for vou in info:
            if (vou.get('total')-vou.get('amount_applied')!=0):
                sheet.write(pos, 0, num, format25)    
                sheet.write(pos, 1, vou.get('date'), format22)
                sheet.write(pos, 2, vou.get('client') or '', format22)
                sheet.write(pos, 3, vou.get('patient') or '', format22)
                sheet.write(pos, 4, vou.get('number') or '', format22)
                sheet.write_number(pos, 5, vou.get('total') or 0, format3)
                sheet.write_number(pos, 6, vou.get('amount_applied') or 0, format3)
                sheet.write_number(pos, 7, vou.get('total')-vou.get('amount_applied'), format3)
                sheet.write(pos, 8, vou.get('invoice') or '-', format22)
                sheet.write(pos, 9, vou.get('account_accounting') or '-', format22)
                sheet.write(pos, 10, vou.get('user') or '', format22)
                total += vou.get('total')
                pos+=1
                num+=1
        sheet.write_number(pos, 5, total or 0, format4)

    def get_data(self, start_date, end_date):
        allowed_company_ids = self.env.context.get('allowed_company_ids') or [self.env.company.id]
        domain = [
            ('state', '=', 'posted'),
            ('payment_type', '=', 'inbound'),
            ('partner_type', '=', 'customer'),
            ('company_id', 'in', allowed_company_ids),
        ]
        if start_date:
            domain.append(('date', '>=', start_date))
        if end_date:
            domain.append(('date', '<=', end_date))

        payments = self.env['account.payment'].search(domain, order='date, name')
        info = []
        for payment in payments:
            move = payment.move_id
            partner_line = move.line_ids.filtered(lambda l: l.partner_id and l.account_id.internal_type in ('receivable', 'payable'))
            partials = partner_line.matched_debit_ids | partner_line.matched_credit_ids
            amount_applied = sum(partial.amount for partial in partials)

            invoices = payment.reconciled_invoice_ids or move.line_ids.mapped('move_id').filtered(lambda m: m.move_type in ('out_invoice', 'out_refund'))
            invoice_names = ', '.join(sorted(set(filter(None, invoices.mapped('name')))))

            info.append({
                'date': self.change_format(payment.date),
                'client': payment.partner_id.name or '',
                'patient': getattr(payment, 'patient_id', False) and payment.patient_id.name or '',
                'number': payment.name,
                'user': payment.create_uid.name or '',
                'amount_applied': amount_applied,
                'invoice': invoice_names,
                'account_accounting': payment.journal_id.default_account_id and (payment.journal_id.default_account_id.code + '  ' + payment.journal_id.default_account_id.name) or '',
                'total': payment.amount,
            })
        return info

    def change_format(self, value):
        if not value:
            return ''
        if isinstance(value, datetime):
            return value.strftime('%d/%m/%Y')
        if isinstance(value, str):
            try:
                parsed = datetime.strptime(value, '%Y-%m-%d')
            except ValueError:
                return value
            return parsed.strftime('%d/%m/%Y')
        if hasattr(value, 'strftime'):
            return value.strftime('%d/%m/%Y')
        return str(value)
