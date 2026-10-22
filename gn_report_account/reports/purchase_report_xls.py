# -*- coding: utf-8 -*-
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
from datetime import datetime,timedelta
import re
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_is_zero
from odoo.tools.mail import html2plaintext
class purchaseReportXls(models.AbstractModel):
    _name = 'report.gn_report_account.purchase_report_xls.xlsx'
    _description = 'Purchase Report XLS'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, lines):
        user_id = data.get('context').get('uid')
        company_name = self.env['res.users'].browse(user_id).company_id.name
        values_in_code = data.get('values_in') or 'local_currency'
        values_in_lbl = _('USD') if values_in_code == 'usd' else _('Local Currency')

        if data.get('report_type') == 'detailed':
            detailed_inf = self.get_invoices(
                data.get('date_from'), data.get('date_to'), values_in_code,
                data.get('report_type'), data.get('state'),
                data.get('per_administrative'), data.get('per_indirect_cost'),
            )
            invoices = detailed_inf.get('info_invoice_line')
            sellers = detailed_inf.get('info_sellers')
        else:
            inf = self.get_invoices(
                data.get('date_from'), data.get('date_to'), values_in_code,
                data.get('report_type'), data.get('state'), 0, 0,
            )

        sheet = workbook.add_worksheet(_('compras'))

        format1 = workbook.add_format({'font_size': 14, 'bottom': True, 'right': True, 'left': True, 'top': True, 'align': 'vcenter', 'bold': True})
        format11 = workbook.add_format({'font_size': 12, 'align': 'center', 'right': True, 'left': True, 'bottom': True, 'top': True, 'bold': True})
        format22 = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
        format22u = workbook.add_format({'font_size': 10, 'align': 'left', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False, 'underline': True})
        format21 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True,'bg_color':'#F3F781'})
        format23 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True,'bg_color':'#0B2161','font_color': 'white'})
        format24 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': False})
        format25 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True,'bg_color':'#21610B','font_color': 'white'})
        format26 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True,'bg_color':'#000000','font_color': 'white'})
        format27 = workbook.add_format({'font_size': 11, 'align': 'center', 'right': False, 'left': False,'bottom': False, 'top': False, 'bold': True,'bg_color':'#F7D358','font_color': 'black'})
        format28 = workbook.add_format({'font_size': 11, 'align': 'center', 'right': True, 'left': True,'bottom': False, 'top': True, 'bold': True,'bg_color':'#F7D358','font_color': 'black'})

        ########### NUMBER FORMAT #######################################
        format3 = workbook.add_format({'align':'right','left':False,'right':False,'bottom': False, 'top': False, 'font_size': 10,'num_format': '#,##0.00'})
        format3u = workbook.add_format({'align':'right','left':False,'right':False,'bottom': False, 'top': False, 'font_size': 10,'num_format': '#,##0.00', 'underline': True})
        format4 = workbook.add_format({'align':'right','left':False,'right':False,'bottom': False, 'top': False, 'bold':True, 'font_size': 10,'num_format': '#,##0.00'})
        format_note = workbook.add_format({
            'font_size': 9, 'text_wrap': True, 'valign': 'vcenter',
            'left': False, 'right': False,
        })
        format5 = workbook.add_format({'align':'right','left':False,'right':False,'bottom': False, 'top': False, 'font_size': 10,'num_format': '.00' + '%'})
        font_size_8 = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8})
        red_mark = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 8,
                                        'bg_color': 'red'})
        justify = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 12})
        font_size_8.set_align('center')
        justify.set_align('justify')
        format1.set_align('center')
        red_mark.set_align('center')

        if data.get('report_type') == 'detailed':
            last_col = 22
            sheet.set_column(0, 0, 3)
            sheet.set_column(1, 1, 11)
            sheet.set_column(2, 2, 14)
            sheet.set_column(3, 3, 12)
            sheet.set_column(4, 4, 28)
            sheet.set_column(5, 5, 12)
            sheet.set_column(6, 6, 12)
            sheet.set_column(7, 7, 12)
            sheet.set_column(8, 9, 22)
            for c in range(10, 22):
                sheet.set_column(c, c, 12)
            sheet.set_column(22, 22, 38)

            sheet.merge_range(0, 0, 0, last_col, company_name, format1)
            sheet.merge_range(1, 0, 1, last_col, _('REPORTE DE COMPRAS (DETALLADO)'), format11)

            sheet.write(3, 1, _('Values in'), format27)
            sheet.write(3, 2, values_in_lbl, format27)

            utility_help = _(
                'Utilidad: Total línea (Subtotal + Impuestos de esta tabla) menos Total precio de costo. '
                'El costo es cantidad × costo estándar del producto (moneda de la compañía), convertido a la moneda '
                'de la factura y reescalado con el mismo factor que el subtotal de la línea respecto a su subtotal '
                'sin impuestos, para alinearlo con Precio unitario. En servicios el costo es 0. '
                'Las filas subrayadas son artículos almacenables/consumibles con costo estándar aplicado; '
                'el pie no suma la columna «Precio costo en producto» (promedio de costos unitarios no es un total).'
            )
            sheet.merge_range(4, 0, 4, last_col, utility_help, format_note)

            hr = 5
            sheet.write(hr, 0, _(''), format23)
            sheet.write(hr, 1, _('Fecha'), format23)
            sheet.write(hr, 2, _('Numero Factura'), format23)
            sheet.write(hr, 3, _('Estado'), format25)
            sheet.write(hr, 4, _('Producto'), format23)
            sheet.write(hr, 5, _('Código producto'), format23)
            sheet.write(hr, 6, _('Catálogo'), format23)
            sheet.write(hr, 7, _('Modelo'), format23)
            sheet.write(hr, 8, _('Cliente'), format23)
            sheet.write(hr, 9, _('Comercial'), format23)
            sheet.write(hr, 10, _('Cantidad'), format23)
            sheet.write(hr, 11, _('Precio Unitario'), format23)
            sheet.write(hr, 12, _('Gravado'), format23)
            sheet.write(hr, 13, _('Exento'), format23)
            sheet.write(hr, 14, _('Exonerado'), format23)
            sheet.write(hr, 15, _('Impuestos'), format23)
            sheet.write(hr, 16, _('Subtotal'), format23)
            sheet.write(hr, 17, _('Descuentos'), format23)
            sheet.write(hr, 18, _('Total'), format25)
            sheet.write(hr, 19, _('Precio costo en producto'), format23)
            sheet.write(hr, 20, _('Total precio de costo'), format23)
            sheet.write(hr, 21, _('Utilidad'), format23)
            sheet.write(hr, 22, _('Observaciones'), format23)

            pos = hr + 1
            array_users = []
            partner_for_user = []
            t_total_cost = 0
            total_total = 0
            total_taxes = 0
            total_subtotal = 0
            total_bruta = 0
            total_discount = 0

            for invoice in invoices:
                vals = {
                    'partner_id': invoice.get('partner_id'),
                    'amount': invoice.get('amount'),
                }
                uid = invoice.get('user_id')
                if uid in array_users:
                    partner_for_user[array_users.index(uid)]['partners'].append(vals)
                else:
                    array_users.append(uid)
                    partner_for_user.append({
                        'user_id': uid,
                        'partners': [vals],
                    })

                total_taxes += invoice.get('taxes')
                total_subtotal += invoice.get('subtotal')
                t_total_cost += invoice.get('total_cost')
                total_total += invoice.get('total')
                total_bruta += invoice.get('u_bruta')
                total_discount += invoice.get('discount')

                emp = invoice.get('emphasize_cost_row')
                f_txt = format22u if emp else format22
                f_num = format3u if emp else format3

                sheet.write(pos, 1, invoice.get('invoice_date'), f_txt)
                sheet.write(pos, 2, invoice.get('number'), f_txt)
                sheet.write(pos, 3, invoice.get('state'), f_txt)
                sheet.write(pos, 4, invoice.get('product'), f_txt)
                sheet.write(pos, 5, invoice.get('product_code') or '', f_txt)
                sheet.write(pos, 6, invoice.get('catalog') or '', f_txt)
                sheet.write(pos, 7, invoice.get('model') or '', f_txt)
                sheet.write(pos, 8, invoice.get('partner_name'), f_txt)
                sheet.write(pos, 9, invoice.get('seller'), f_txt)
                sheet.write(pos, 10, invoice.get('qty'), format24)
                sheet.write_number(pos, 11, invoice.get('price_unit') or 0, f_num)
                sheet.write_number(pos, 12, invoice.get('taxed') or 0, f_num)
                sheet.write_number(pos, 13, invoice.get('exempt') or 0, f_num)
                sheet.write_number(pos, 14, invoice.get('exonerate') or 0, f_num)
                sheet.write_number(pos, 15, invoice.get('taxes') or 0, f_num)
                sheet.write_number(pos, 16, invoice.get('subtotal') or 0, f_num)
                sheet.write_number(pos, 17, invoice.get('discount') or 0, f_num)
                sheet.write_number(pos, 18, invoice.get('total') or 0, f_num)
                sheet.write_number(pos, 19, invoice.get('unit_cost') or 0, f_num)
                sheet.write_number(pos, 20, invoice.get('total_cost') or 0, f_num)
                sheet.write_number(pos, 21, invoice.get('u_bruta') or 0, f_num)
                sheet.write(pos, 22, invoice.get('observations') or '', format22)
                pos += 1

            sheet.write(pos, 0, _('Totales'), format24)
            sheet.write_number(pos, 15, total_taxes or 0, format4)
            sheet.write_number(pos, 16, total_subtotal or 0, format4)
            sheet.write_number(pos, 17, total_discount or 0, format4)
            sheet.write_number(pos, 18, total_total or 0, format4)
            sheet.write(pos, 19, '—', format4)
            sheet.write_number(pos, 20, t_total_cost or 0, format4)
            sheet.write_number(pos, 21, total_bruta or 0, format4)

            ############################## PAGE 2 ###########################################
            sheet2 = workbook.add_worksheet(_('Sellers'))

            sheet2.set_column(0, 0, 40)
            sheet2.set_column(1, 1, 40)
            sheet2.set_column(2, 2, 15)
            sheet2.set_column(3, 3, 15)
            sheet2.set_column(4, 4, 15)

            sheet2.write(4, 0, _('Seller'), format23)
            sheet2.write(4, 1, _('Client'), format23)
            sheet2.write(4, 2, _('Sum-Subtotal'), format23)
            pos2 = 5
            total_subtotal = 0
            for seller in sellers:
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
        else:
            sheet.set_column(0, 0, 3)
            sheet.set_column(1, 1, 17)
            sheet.set_column(2, 2, 40)
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
            sheet.merge_range('A2:O2', _('REPORTE DE COMPRAS'), format11)
            
            sheet.write(3, 1, _('Values in'), format27)
            sheet.write(3, 2, values_in_lbl, format27)
            
            sheet.write(4, 0, _(''), format23)
            sheet.write(4, 1, _('Numero Factura'), format23)
            sheet.write(4, 2, _('Cliente'), format23)
            sheet.write(4, 3, _('Fecha'), format23)
            sheet.write(4, 4, _('Estado'), format23)
            sheet.write(4, 5, _('Comercial'), format23)
            sheet.write(4, 6, _('Numero de Pagos'), format23)
            sheet.write(4, 7, _('Diarios de Pago'), format23)
            sheet.write(4, 8, _('Monto de Pago'), format23)
            # sheet.write(4, 9, _('Precio de Costo'), format23)
            sheet.write(4, 9, _('Descuento'), format23)
            sheet.write(4, 10, _('Exonerado'), format23)
            sheet.write(4, 11, _('Exento'), format23)
            sheet.write(4, 12, _('Gravado'), format23)
            sheet.write(4, 13, _('Impuestos'), format23)
            sheet.write(4, 14, _('Subtotal'), format23)
            sheet.write(4, 15, _('Total'), format23)
            sheet.write(4, 16, _('Residual'), format23)

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

            for invoices in inf:
                sheet.write(pos, 1, invoices.get('number'), format22)
                sheet.write(pos, 2, invoices.get('client'), format22)
                sheet.write(pos, 3, invoices.get('invoice_date'), format22)
                sheet.write(pos, 4, invoices.get('state'), format22)
                sheet.write(pos, 5, invoices.get('seller'), format22)
                sheet.write(pos, 6, invoices.get('pay_number'), format22)
                sheet.write(pos, 7, invoices.get('journal'), format22)
                sheet.write_number(pos, 8, invoices.get('pay_amounts'), format3)
                # sheet.write_number(pos, 9, invoices.get('cost_prices'), format3)
                sheet.write_number(pos, 9, invoices.get('discount'), format3)
                sheet.write_number(pos, 10, invoices.get('exonerate'), format3)
                sheet.write_number(pos, 11, invoices.get('exempt'), format3)
                sheet.write_number(pos, 12, invoices.get('taxed'), format3)
                sheet.write_number(pos, 13, invoices.get('taxes'), format3)
                sheet.write_number(pos, 14, invoices.get('subtotal'), format3)
                sheet.write_number(pos, 15, invoices.get('total'), format3)
                sheet.write_number(pos, 16, invoices.get('residual'), format3)
                t_discount += invoices.get('discount')
                t_taxes += invoices.get('taxes')
                t_subtotal += invoices.get('subtotal')
                t_total += invoices.get('total')
                t_residual += invoices.get('residual')
                t_pays += invoices.get('pay_amounts')
                t_exonerate += invoices.get('exonerate')
                t_exempt += invoices.get('exempt')
                t_taxed += invoices.get('taxed')
                pos+=1
            sheet.write_number(pos, 8, t_pays or 0, format4)
            sheet.write_number(pos, 9, t_discount or 0, format4)
            sheet.write_number(pos, 10, t_exonerate or 0, format4)
            sheet.write_number(pos, 11, t_exempt or 0, format4)
            sheet.write_number(pos, 12, t_taxed or 0, format4)
            sheet.write_number(pos, 13, t_taxes or 0, format4)
            sheet.write_number(pos, 14, t_subtotal or 0, format4)
            sheet.write_number(pos, 15, t_total or 0, format4)
            sheet.write_number(pos, 16, t_residual or 0, format4)

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

    def _invoice_observations(self, invoice):
        parts = []
        if invoice.ref:
            parts.append(invoice.ref.strip())
        if invoice.narration:
            parts.append(html2plaintext(invoice.narration or '').strip())
        return ' | '.join(p for p in parts if p)

    def get_invoices(self, date_from, date_to, values_in_code, report_type, state, per_administrative, per_indirect_cost):
        allowed_company_ids = self.env.context.get('allowed_company_ids') or [self.env.company.id]
        domain = [
            ('move_type', 'in', ['in_invoice', 'in_refund', 'in_receipt']),
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
                if values_in_code == 'usd' and invoice.currency_id.name == 'USD':
                    invoice_subtotal = invoice.amount_untaxed
                elif values_in_code == 'usd' and invoice.currency_id.name != 'USD':
                    invoice_subtotal = invoice.amount_untaxed*rate
                elif values_in_code != 'usd' and invoice.currency_id.name == 'USD':
                    invoice_subtotal = invoice.amount_untaxed/rate
                elif values_in_code != 'usd' and invoice.currency_id.name != 'USD':
                    invoice_subtotal = invoice.amount_untaxed
                values = {
                    'client':invoice.partner_id.name,
                    'subtotal':invoice_subtotal,
                    'id':invoice.partner_id.id
                }

                if invoice.user_id.id in seller_ids:
                    info_sellers[seller_ids.index(invoice.user_id.id)]['clients'].append(values)
                else:
                    seller_ids.append(invoice.user_id.id)
                    info_sellers.append({
                        'seller':invoice.user_id.name or invoice.create_uid.name or '',
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

                    if values_in_code == 'usd' and invoice.currency_id.name == 'USD':
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
                    elif values_in_code == 'usd' and invoice.currency_id.name != 'USD':
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
                    elif values_in_code != 'usd' and invoice.currency_id.name == 'USD':
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
                    elif values_in_code != 'usd' and invoice.currency_id.name != 'USD':
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
                        state = _('Pagada')
                    elif invoice.payment_state == 'not_paid':
                        state = _('Sin Pagar')
                    elif invoice.payment_state == 'in_payment':
                        state = _('En Proceso de Pago')
                    elif invoice.payment_state == 'partial':
                        state = _('Parcialmente Pagado')

                    discount = 0
                    if (line.discount or 0.0) > 0:
                        discount = line.quantity * line.price_unit * (line.discount or 0.0) / 100.0

                    product = line.product_id
                    qty = line.quantity or 0.0
                    product_code = (product.default_code if product else '') or ''
                    catalog = ''
                    model = ''
                    if product:
                        tmpl = product.product_tmpl_id
                        if 'gn_labhospy_catalog_code' in tmpl._fields:
                            catalog = tmpl.gn_labhospy_catalog_code or ''
                        if 'gn_labhospy_model' in tmpl._fields:
                            model = tmpl.gn_labhospy_model or ''
                    if not product or product.type == 'service':
                        unit_cost = 0.0
                        total_cost = 0.0
                        emphasize_cost_row = False
                    else:
                        emphasize_cost_row = product.type in ('product', 'consu')
                        company = invoice.company_id
                        comp_cur = company.currency_id
                        inv_cur = invoice.currency_id
                        conv_date = invoice.invoice_date or invoice.date or fields.Date.context_today(self)
                        std_unit_inv = comp_cur._convert(
                            product.standard_price,
                            inv_cur,
                            company,
                            conv_date,
                        )
                        std_total_inv = std_unit_inv * qty
                        base_sub = line.price_subtotal or 0.0
                        if base_sub and not float_is_zero(base_sub, 2):
                            factor = line_subtotal / base_sub
                        else:
                            factor = 1.0
                        total_cost = std_total_inv * factor
                        unit_cost = total_cost / qty if qty else 0.0

                    total = line_subtotal + taxes
                    u_bruta = total - total_cost
                    ic = 0
                    administrative = 0
                    if per_indirect_cost:
                        ic = line_subtotal * (per_indirect_cost/100)
                    if per_administrative:
                        administrative = line_subtotal * (per_administrative/100)
                    total_spends = ic + administrative
                    utility = u_bruta - total_spends
                    
                    if float_is_zero(total, 2):
                        net = 0
                        ub = 0
                    else:
                        net = utility / total
                        ub = u_bruta / total

                    info_invoice_line.append({
                        'number': invoice.supplier_invoice_number,
                        'product': line.product_id.name or line.name or '',
                        'product_code': product_code,
                        'catalog': catalog,
                        'model': model,
                        'observations': self._invoice_observations(invoice),
                        'emphasize_cost_row': emphasize_cost_row,
                        'partner_name': invoice.partner_id.name,
                        'invoice_date': self.change_format(invoice.invoice_date),
                        'seller': invoice.user_id.name or invoice.create_uid.name or '',
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
                        'category': line.product_id.categ_id.name,
                        'total_cost': total_cost,
                        'unit_cost': unit_cost,
                    })
                    days = ''
                count += 1
            return {'info_invoice_line':info_invoice_line, 'info_sellers':info_sellers}
        else:
            info = []
            for invoice in obj_invoice:
                if invoice.payment_state == 'paid':
                    state = _('Pagada')
                elif invoice.payment_state == 'not_paid':
                    state = _('Sin Pagar')
                elif invoice.payment_state == 'in_payment':
                    state = _('En Proceso de Pago')
                elif invoice.payment_state == 'partial':
                    state = _('Parcialmente Pagado')

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
                    invoice_subtotal = -(invoice.amount_untaxed_signed)
                    invoice_amount_total = -(invoice.amount_local)
                    invoice_amount_residual = -(invoice.amount_residual_signed)
                    invoice_amount_tax = -(invoice.amount_tax_signed)
                    invoice_exonerate_amount = invoice.exonerate_amount * rate
                    invoice_exempt_sale_amount = invoice.exempt_sale_amount * rate
                    if invoice.amount_tax_15_per > 0:
                        invoice_amount_tax_15_per = -(invoice.amount_untaxed_signed)
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
                
                info.append({
                    'number': invoice.supplier_invoice_number or invoice.name,
                    'client': invoice.partner_id.name or '',
                    'invoice_date': self.change_format(invoice.invoice_date),
                    'seller': invoice.user_id.name or invoice.create_uid.name or '',
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
