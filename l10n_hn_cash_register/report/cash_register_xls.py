# -*- coding: utf-8 -*-
from odoo import _, models
import io
import base64
from datetime import datetime, date as dt_date

class cashRegisterXls(models.AbstractModel):
    _name = 'report.l10n_hn_cash_register.cash_register_xls.xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Cash Register XLS Report'

    def generate_xlsx_report(self, workbook, data, lines):
        info, cashiers = self.get_invoices(data.get('date_from'),data.get('date_to'),data.get('cashier_ids'))
        
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


        # Crear hoja principal de arqueo de caja
        sheet = workbook.add_worksheet('Arqueo de Caja')
        
        # Combinar todos los datos de todos los cajeros
        all_invoices = []
        all_journals = {}
        for cash in info:
            for invoice in cash.get('info', []):
                all_invoices.append(invoice)
                # Acumular por diario
                journal_name = invoice.get('journal')
                if journal_name:
                    if journal_name in all_journals:
                        all_journals[journal_name] += invoice.get('total', 0)
                    else:
                        all_journals[journal_name] = invoice.get('total', 0)
        
        # Obtener nombres de cajeros
        cashier_names = ', '.join([c.get('cashier', '') for c in info if c.get('cashier')])
        
        # Configurar anchos de columnas básicas
        sheet.set_column(0, 0, 5)   # #
        sheet.set_column(1, 1, 12)  # Fecha de Pago
        sheet.set_column(2, 2, 25)  # Número de Pago
        sheet.set_column(3, 3, 30)  # Cliente
        sheet.set_column(4, 4, 30)  # Diario de Pago
        sheet.set_column(5, 5, 25)  # Número de Factura
        sheet.set_column(6, 6, 15)  # Estado de Factura
        sheet.set_column(7, 7, 15)  # Monto

        sheet.merge_range('B4:G4', self.env.user.company_id.name, format1)
        sheet.merge_range('B5:G5', 'ARQUEO DE CAJA DIARIO', format11)
        
        buf_image = io.BytesIO(base64.b64decode(self.env.user.company_id.logo))
        sheet.insert_image('A1', "any_name.png", {'image_data': buf_image, 'x_scale': 0.2, 'y_scale': 0.2})
        
        sheet.write(6, 1, 'Desde: %s' % (data.get('date_from')), format22)
        sheet.write(6, 2, 'Hasta: %s' % (data.get('date_to')), format22)
        sheet.write(6, 3, 'Cajeros: %s' % (cashier_names or 'Todos'), format22)

        pos = 9
        total = 0
        num = 1
        
        if all_invoices and len(all_invoices) > 0:
            # Encabezados de tabla
            sheet.write(8, 0, '#', format21)
            sheet.write(8, 1, 'Fecha de Pago', format21)
            sheet.write(8, 2, 'Número de Pago', format21)
            sheet.write(8, 3, 'Cliente', format21)
            sheet.write(8, 4, 'Diario de Pago', format21)
            sheet.write(8, 5, 'Número de Factura', format21)
            sheet.write(8, 6, 'Estado de Factura', format21)
            sheet.write(8, 7, 'Monto', format21)
            
            # Datos
            for invoice in all_invoices:
                sheet.write(pos, 0, num, format22)
                sheet.write(pos, 1, invoice.get('date'), format22)
                sheet.write(pos, 2, invoice.get('number'), format22)
                sheet.write(pos, 3, invoice.get('partner'), format22)
                sheet.write(pos, 4, invoice.get('journal'), format22)
                sheet.write(pos, 5, invoice.get('invoice_numbers'), format22)
                sheet.write(pos, 6, invoice.get('invoice_state'), format22)
                sheet.write_number(pos, 7, invoice.get('total') or 0, format3)
                total += invoice.get('total') or 0
                pos += 1
                num += 1

            # Total
            sheet.write(pos, 6, 'Total General:', format24)
            sheet.write_number(pos, 7, total, format4)
            pos += 3
            
            # Resumen por diarios
            sheet.write(pos, 2, 'RESUMEN POR DIARIO', format23)
            pos += 1
            sheet.write(pos, 2, 'Diario', format21)
            sheet.write(pos, 3, 'Monto', format21)
            pos += 1
            
            for journal_name, journal_total in all_journals.items():
                sheet.write(pos, 2, journal_name, format22)
                sheet.write_number(pos, 3, journal_total, format3)
                pos += 1
            
            # Total resumen
            sheet.write(pos, 2, 'Total:', format24)
            sheet.write_number(pos, 3, total, format4)
            pos += 2

            # Observaciones y firmas
            sheet.write(pos, 1, 'Observaciones:', format24)
            pos += 1
            sheet.merge_range(pos, 1, pos, 6, '', format26)
            pos += 3

            sheet.merge_range(pos, 2, pos+2, 2, '', format22)
            sheet.write(pos+3, 2, 'Firma del Cajero', format25)

            sheet.merge_range(pos, 4, pos+2, 4, '', format22)
            sheet.write(pos+3, 4, 'Firma del Supervisor', format25)

        # ####################### Facturas abiertas + parciales (2da hoja) ########################################
        all_open_invoices = []
        all_partial_invoices = []
        for cash in info:
            for open_inv in cash.get('open_invoice', []):
                all_open_invoices.append(open_inv)
            for part_inv in cash.get('partial_invoice', []):
                all_partial_invoices.append(part_inv)

        if all_open_invoices or all_partial_invoices:
            sheet2 = workbook.add_worksheet('Facturas pendientes')
            sheet2.set_column(0, 0, 5)   # #
            sheet2.set_column(1, 1, 20)  # Número Factura
            sheet2.set_column(2, 2, 28)  # Cliente
            sheet2.set_column(3, 3, 14)  # Fecha Factura
            sheet2.set_column(4, 4, 14)  # Total
            sheet2.set_column(5, 5, 14)  # Saldo pendiente / Estado

            sheet2.merge_range('B4:G4', self.env.user.company_id.name, format1)
            sheet2.merge_range('B5:G5', 'FACTURAS PENDIENTES', format11)

            buf_image = io.BytesIO(base64.b64decode(self.env.user.company_id.logo))
            sheet2.insert_image('A1', "any_name.png", {'image_data': buf_image, 'x_scale': 0.2, 'y_scale': 0.2})

            sheet2.write(6, 1, 'Desde: %s' % (data.get('date_from')), format22)
            sheet2.write(6, 2, 'Hasta: %s' % (data.get('date_to')), format22)
            sheet2.write(6, 3, 'Cajeros: %s' % (cashier_names or 'Todos'), format22)

            pos = 8

            def _write_open_section():
                nonlocal pos
                sheet2.merge_range(pos, 0, pos, 5, _('FACTURAS ABIERTAS (sin pago o en pago)'), format23)
                pos += 1
                sheet2.write(pos, 0, '#', format21)
                sheet2.write(pos, 1, _('Número de Factura'), format21)
                sheet2.write(pos, 2, _('Cliente'), format21)
                sheet2.write(pos, 3, _('Fecha de Factura'), format21)
                sheet2.write(pos, 4, _('Total'), format21)
                sheet2.write(pos, 5, _('Estado de pago'), format21)
                pos += 1
                sec_total = 0
                num_local = 1
                for open_inv in all_open_invoices:
                    sheet2.write(pos, 0, num_local, format22)
                    sheet2.write(pos, 1, open_inv.get('number'), format22)
                    sheet2.write(pos, 2, open_inv.get('partner'), format22)
                    sheet2.write(pos, 3, open_inv.get('date_invoice'), format22)
                    sheet2.write_number(pos, 4, open_inv.get('total') or 0, format3)
                    sheet2.write(pos, 5, open_inv.get('payment_state_label') or '', format22)
                    sec_total += open_inv.get('total') or 0
                    pos += 1
                    num_local += 1
                sheet2.write(pos, 3, _('Subtotal sección'), format24)
                sheet2.write_number(pos, 4, sec_total, format4)
                pos += 2

            def _write_partial_section():
                nonlocal pos
                sheet2.merge_range(pos, 0, pos, 5, _('FACTURAS PARCIALMENTE PAGADAS'), format23)
                pos += 1
                sheet2.write(pos, 0, '#', format21)
                sheet2.write(pos, 1, _('Número de Factura'), format21)
                sheet2.write(pos, 2, _('Cliente'), format21)
                sheet2.write(pos, 3, _('Fecha de Factura'), format21)
                sheet2.write(pos, 4, _('Total'), format21)
                sheet2.write(pos, 5, _('Saldo pendiente'), format21)
                pos += 1
                sec_total = 0
                sec_residual = 0
                num_local = 1
                for part_inv in all_partial_invoices:
                    sheet2.write(pos, 0, num_local, format22)
                    sheet2.write(pos, 1, part_inv.get('number'), format22)
                    sheet2.write(pos, 2, part_inv.get('partner'), format22)
                    sheet2.write(pos, 3, part_inv.get('date_invoice'), format22)
                    sheet2.write_number(pos, 4, part_inv.get('total') or 0, format3)
                    sheet2.write_number(pos, 5, part_inv.get('residual') or 0, format3)
                    sec_total += part_inv.get('total') or 0
                    sec_residual += part_inv.get('residual') or 0
                    pos += 1
                    num_local += 1
                sheet2.write(pos, 3, _('Subtotal sección'), format24)
                sheet2.write_number(pos, 4, sec_total, format4)
                sheet2.write_number(pos, 5, sec_residual, format4)
                pos += 1

            if all_open_invoices:
                _write_open_section()
            if all_partial_invoices:
                _write_partial_section()

            # ####################### Receipts ########################################
            # if len(cash.get('voucher')) > 0:
            #     sheet4 = workbook.add_worksheet(_('Receipts %s')%(cash.get('cashier')))
            #     sheet4.set_column(0, 0, 5)
            #     sheet4.set_column(1, 1, 15)
            #     sheet4.set_column(2, 2, 25)
            #     sheet4.set_column(3, 3, 25)
            #     sheet4.set_column(4, 4, 25)
            #     sheet4.set_column(5, 5, 50)
            #     sheet4.set_column(6, 6, 25)
            #     sheet4.set_column(7, 7, 15)

            #     sheet4.merge_range('D4:G4', self.env.user.company_id.name, format1)
            #     sheet4.merge_range('D5:G5', _('Daily Cash Count').upper(), format11)
                
            #     buf_image = io.BytesIO(base64.b64decode(self.env.user.company_id.logo))
            #     sheet4.insert_image('C1', "any_name.png", {'image_data': buf_image, 'x_scale': 0.2, 'y_scale': 0.2})
                
            #     sheet4.write(6, 3, _('From : %s')%(data.get('date_from')), format22)
            #     sheet4.write(6, 4, _('To : %s')%(data.get('date_to')), format22)
            #     sheet4.write(6, 5, _('Cashier : %s')%(cash.get('cashier')), format22)

            #     pos = 9
            #     total = 0
            #     num = 1
            #     sheet4.write(8, 0, '#', format21)
            #     sheet4.write(8, 1, _('Pay Date'), format21)
            #     sheet4.write(8, 2, _('Pay Number'), format21)
            #     sheet4.write(8, 3, _('State'), format21)
            #     sheet4.write(8, 4, _('Journal'), format21)
            #     sheet4.write(8, 5, _('Partner'), format21)
            #     sheet4.write(8, 6, _('Total'), format21)
            #     for voucher in cash.get('voucher'):
            #         sheet4.write(pos, 0, num, format21)
            #         sheet4.write(pos, 1, voucher.get('date'), format22)
            #         sheet4.write(pos, 2, voucher.get('number'), format22)
            #         sheet4.write(pos, 3, voucher.get('state'), format22)
            #         sheet4.write(pos, 4, voucher.get('journal'), format22)
            #         sheet4.write(pos, 5, voucher.get('partner'), format22)
            #         sheet4.write_number(pos, 6, voucher.get('total'), format3)
            #         total+=invoice.get('total')
            #         pos+=1
            #         num+=1


    def get_invoices(self,date_from,date_to,cashier_ids):
        # Buscar automáticamente todos los diarios de tipo banco y efectivo
        journal_ids = self.env['account.journal'].search([('type', 'in', ['bank', 'cash'])]).ids
        account_payment = self.env['account.payment']
        domain = [('payment_type','=','inbound'),('state','in',['posted','paid','cancel']),('journal_id','in',journal_ids)]
        # account_voucher = self.env['account.voucher']
        invoice = self.env['account.move']
        domain_invoice = [('state','in',['cancel','posted'])]
        # domain_voucher = [('state','in',['posted'])]
        info_invoice = []
        if date_from:
            # domain_voucher.append(('date','>=',date_from))
            domain.append(('date','>=',date_from))
            domain_invoice.append(('invoice_date','>=',date_from))
        if date_to:
            # domain_voucher.append(('date','<=',date_to))
            domain.append(('date','<=',date_to))
            domain_invoice.append(('invoice_date','<=',date_to))
        if cashier_ids:
            domain.append(('create_uid', 'in', cashier_ids))
        domain.append(('journal_id', 'in', journal_ids))
        # domain_voucher.append(('user_id','in',cashier_ids))
        if cashier_ids:
            domain_invoice.append(('user_id', 'in', cashier_ids))

        obj_payment = account_payment.search(domain)
        obj_create_uid_ids = []
        create_uid_ids = []
        
        # obj_voucher = account_voucher.search(domain_voucher)
        invoice_obj = invoice.search(domain_invoice)
        journal_array = []
        journal_ids = []
        info_cashier = []
        cancel_invoice = []
        open_invoice = []
        partial_invoice = []
        vouchers = []
        for payment in obj_payment.sorted():
            if not payment.create_uid.id in obj_create_uid_ids:
                obj_create_uid_ids.append(payment.create_uid.id)
                create_uid_ids.append({
                    'id' : payment.create_uid.id,
                    'name': payment.create_uid.name,
                })
            # print('====>>>>payment.name',payment.name)
            invoice_ids = []
            for invoice_id in payment.reconciled_invoice_ids:
                invoice_ids.append({
                    'id': invoice_id.id,
                    'name' : invoice_id.name,
                    'state' : invoice_id.state,
                    'amount_total' : invoice_id.amount_total,
                    'amount_residual' : invoice_id.amount_residual,
                })
                # print('====>>>>payment.reconciled_invoice_ids',invoice_id)
            vals = {
                'id' : payment.id,
                'date_payment' : self.change_format(str(payment.date)),
                'number_payment' : payment.name,
                'journal_id' : payment.journal_id.name,
                'imvoice_ids' : invoice_ids,
                'state' : payment.state,
                'amount' : payment.amount,
            }
            info_cashier.append(vals)
            # print('====>>>>payment.invoice_line_ids',payment.invoice_line_ids)
            # for line in payment.invoice_lines:
            #     print('====>>>>line',line.invoice_id.name)
            # for line in payment.invoice_line_ids:
            #     print('====>>>>line',line)
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f'=== Cash Register Excel Debug ===')
        _logger.info(f'Total payments found: {len(obj_payment)}')
        
        cashiers = self.env['res.users'].browse(cashier_ids)
        for ca in cashiers:
            _logger.info(f'Processing cashier: {ca.name}')
            for pay in obj_payment.filtered(lambda x: x.create_uid.id == ca.id):
                _logger.info(f'  Payment: {pay.name} - Journal: {pay.journal_id.code} - Amount: {pay.amount}')
                _logger.info(f'  Reconciled invoices count: {len(pay.reconciled_invoice_ids)}')
                
                # Obtener facturas reconciliadas
                invoice_names = ', '.join(pay.reconciled_invoice_ids.mapped('name')) if pay.reconciled_invoice_ids else 'Sin Factura'
                
                # Determinar estado del pago
                if pay.state == 'draft':
                    payment_state = 'Borrador'
                elif pay.state == 'posted':
                    payment_state = 'Publicado'
                elif pay.state == 'paid':
                    payment_state = 'Pagado'
                elif pay.state == 'cancel':
                    payment_state = 'Cancelado'
                else:
                    payment_state = pay.state
                
                # Determinar estado de la factura
                should_include = False
                if pay.reconciled_invoice_ids:
                    first_invoice = pay.reconciled_invoice_ids[0]
                    if first_invoice.payment_state == 'paid':
                        invoice_state = 'Pagado'
                        should_include = True
                    elif first_invoice.payment_state == 'partial':
                        invoice_state = 'Parcial'
                        should_include = True
                    elif first_invoice.payment_state == 'not_paid':
                        invoice_state = 'No Pagado'
                        should_include = False
                    elif first_invoice.payment_state == 'in_payment':
                        invoice_state = 'En Pago'
                        should_include = True
                    else:
                        invoice_state = first_invoice.payment_state or ''
                        should_include = False
                else:
                    invoice_state = 'Sin Factura'
                    should_include = False
                
                _logger.info(f'    Journal: {pay.journal_id.name} ({pay.journal_id.code}) - Include: {should_include}')
                
                # Solo agregar si la factura está pagada o parcialmente pagada
                if should_include:
                    # Agregar línea de pago (estructura simplificada)
                    info_invoice.append({
                        'date': self.change_format(pay.date),
                        'invoice_numbers': invoice_names,
                        'number': pay.name,
                        'total': pay.amount,
                        'journal': pay.journal_id.name,
                        'comercial': pay.create_uid.name,
                        'partner': pay.partner_id.name if pay.partner_id else 'Sin Cliente',
                        'state': payment_state,
                        'invoice_state': invoice_state,
                    })
                    
                    # Acumular totales por diario (solo para pagos incluidos)
                    if pay.journal_id.id in journal_ids:
                        journal_array[journal_ids.index(pay.journal_id.id)]['total'] += pay.amount
                    else:
                        journal_ids.append(pay.journal_id.id)
                        journal_array.append({
                            'journal': pay.journal_id.name,
                            'total': pay.amount,
                        })
                    
                    _logger.info(f'    Added invoice line for payment {pay.name}')
                else:
                    _logger.info(f'    Skipped payment {pay.name} - Invoice state: {invoice_state}')
            
            # for vou in obj_voucher.filtered(lambda x: x.user_id.id == ca.id):
            #     data = False
            #     if vou.payment_journal_id.code == 'TCB':
            #         data = {
            #             'date': self.change_format(vou.date),
            #             'number': vou.number,
            #             'total': vou.amount,
            #             'journal': vou.journal_id.name,
            #             'comercial': vou.user_id.name,
            #             'journal_voucher': vou.payment_journal_id.name,
            #             'partner': vou.partner_id.name,
            #             'state': self.get_state(invoice.state),
            #             'tcb': vou.amount,
            #             'csh1': 0,
            #             'tcf': 0,
            #             'tcb2': 0,
            #             'csh2': 0,
            #         }
            #     elif vou.payment_journal_id.code == 'TCF':
            #         data = {
            #             'date': self.change_format(vou.date),
            #             'number': vou.number,
            #             'total': vou.amount,
            #             'journal': vou.journal_id.name,
            #             'comercial': vou.user_id.name,
            #             'journal_voucher': vou.payment_journal_id.name,
            #             'partner': vou.partner_id.name,
            #             'state': self.get_state(invoice.state),
            #             'tcb': 0,
            #             'csh1': 0,
            #             'tcf': vou.amount,
            #             'tcb2': 0,
            #             'csh2': 0,
            #         }
            #     elif vou.payment_journal_id.code == 'CSH1':
            #         data = {
            #             'date': self.change_format(vou.date),
            #             'number': vou.number,
            #             'total': vou.amount,
            #             'journal': vou.journal_id.name,
            #             'comercial': vou.user_id.name,
            #             'journal_voucher': vou.payment_journal_id.name,
            #             'partner': vou.partner_id.name,
            #             'state': self.get_state(invoice.state),
            #             'tcb': 0,
            #             'csh1': vou.amount,
            #             'tcf': 0,
            #             'tcb2': 0,
            #             'csh2': 0,
            #         }
            #     elif vou.payment_journal_id.code == 'CSH2':
            #         data = {
            #             'date': self.change_format(vou.date),
            #             'number': vou.number,
            #             'total': vou.amount,
            #             'journal': vou.journal_id.name,
            #             'comercial': vou.user_id.name,
            #             'journal_voucher': vou.payment_journal_id.name,
            #             'partner': vou.partner_id.name,
            #             'state': self.get_state(invoice.state),
            #             'tcb': 0,
            #             'csh1': 0,
            #             'tcf': 0,
            #             'tcb2': 0,
            #             'csh2': vou.amount,
            #         }
            #     elif vou.payment_journal_id.code == 'TCB2':
            #         data = {
            #             'date': self.change_format(vou.date),
            #             'number': vou.number,
            #             'total': vou.amount,
            #             'journal': vou.journal_id.name,
            #             'comercial': vou.user_id.name,
            #             'journal_voucher': vou.payment_journal_id.name,
            #             'partner': vou.partner_id.name,
            #             'state': self.get_state(invoice.state),
            #             'tcb': 0,
            #             'csh1': 0,
            #             'tcf': 0,
            #             'tcb2': vou.amount,
            #             'csh2': 0,
            #         }
            #     if data:
            #         info_invoice.append(data)
            #         vouchers.append(data)
                    
            #     if vou.payment_journal_id.code in ['CSH1','TCB','TCF','CSH2','TCB2']:
            #         if vou.payment_journal_id.id in journal_ids:
            #             journal_array[journal_ids.index(vou.payment_journal_id.id)]['total']+= vou.amount
            #         else:
            #             journal_ids.append(vou.payment_journal_id.id)
            #             journal_array.append({
            #                 'journal': vou.payment_journal_id.name,
            #                 'total': vou.amount,
            #             })

            for inv in invoice_obj.filtered(lambda x: x.user_id.id == ca.id):
                if inv.state == 'cancel':
                    cancel_invoice.append({
                        'date_invoice': self.change_format(inv.invoice_date),
                        'number': inv.name,
                        'total': inv.amount_total,
                        'partner': inv.partner_id.name,
                    })
                    continue
                if inv.state != 'posted' or inv.payment_state == 'paid':
                    continue
                line_common = {
                    'date_invoice': self.change_format(inv.invoice_date),
                    'number': inv.name,
                    'total': inv.amount_total,
                    'residual': inv.amount_residual,
                    'partner': inv.partner_id.name,
                    'payment_state_label': self._get_invoice_payment_state_label(inv),
                }
                if inv.payment_state == 'partial':
                    partial_invoice.append(line_common)
                elif inv.payment_state in ('not_paid', 'in_payment'):
                    open_invoice.append(line_common)

            _logger.info(f'Cashier {ca.name} - Total invoice lines: {len(info_invoice)}')
            _logger.info(f'Cashier {ca.name} - Total journals: {len(journal_array)}')
            _logger.info(f'Cashier {ca.name} - Open invoices: {len(open_invoice)}')
            _logger.info(f'Cashier {ca.name} - Partial invoices: {len(partial_invoice)}')
            
            info_cashier.append({
                'cashier': ca.name,
                'cashier_id': ca.id,
                'info': info_invoice if info_invoice else [],
                'journals': journal_array if journal_array else [],
                'cancel_invoice': cancel_invoice if cancel_invoice else [],
                'open_invoice': open_invoice if open_invoice else [],
                'partial_invoice': partial_invoice if partial_invoice else [],
                'voucher': vouchers if vouchers else []
            })
            info_invoice = []
            journal_array = []
            journal_ids = []
            open_invoice = []
            partial_invoice = []
            cancel_invoice = []
            vouchers = []
        
        _logger.info(f'Total cashiers with data: {len(info_cashier)}')
        _logger.info(f'=== End Cash Register Excel Debug ===')
        return info_cashier,create_uid_ids

    def _get_invoice_payment_state_label(self, invoice):
        mapping = {
            'not_paid': _('Pendiente de pago'),
            'partial': _('Parcialmente pagada'),
            'in_payment': _('En pago'),
            'paid': _('Pagada'),
            'reversed': _('Reversada'),
        }
        return mapping.get(invoice.payment_state, _('Contabilizada'))

    def get_state(self,state):
        if state == 'draft':
            return _('Draft')
        elif state == 'posted':
            return _('Validated')
        elif state == 'reconciled':
            return _('Reconciled')
        elif state in ('cancel', 'cancelled'):
            return _('Cancelled')

    def get_journal_pays(self,journal,residual):
        info_lines = []
        array_journal = []
        if journal.id in array_journal:
            pass
        else:
            array_journal.append(journal.id)
            info_lines.append({
                'journal': journal.name or _('ANULATED'),
                'total': 0,  # Este valor debería venir como parámetro
                'id': journal.id
            })
        if residual != 0:
            info_lines.append({
                'journal': _('Credit'),
                'total': residual,
                'id': 0
            })
        return info_lines

    def change_format(self, date_value):
        if not date_value:
            return ''
        if isinstance(date_value, dt_date):
            date_str = date_value.strftime('%Y-%m-%d')
        else:
            date_str = str(date_value)
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').strftime('%d/%m/%Y')
        except ValueError:
            return date_str
