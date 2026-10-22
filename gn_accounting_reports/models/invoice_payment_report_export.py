# -*- coding: utf-8 -*-
"""Exportaciones del tablero Facturas y pagos."""

import base64
import csv
import io

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class InvoicePaymentReportExport(models.AbstractModel):
    _name = 'gn.accounting.invoice.payment.export'
    _description = 'Exportación Facturas y pagos Premium'

    @api.model
    def export_data(self, filters=None, export_format='csv', options=None):
        service = self.env['gn.accounting.invoice.payment.service']
        service._check_report_access()
        parsed = service._parse_filters(filters)
        company = parsed['company']
        max_rows = company.inv_pay_export_max_sync_rows or 10000
        rows = service._transform_view_mode(
            service._collect_rows(parsed), parsed['view_mode']
        )
        if len(rows) > max_rows:
            raise UserError(_(
                'El resultado tiene %(count)s filas; el máximo para exportación '
                'síncrona es %(max)s. Acote los filtros.',
                count=len(rows), max=max_rows,
            ))
        public_rows = [service._public_row(r) for r in rows]
        fmt = (export_format or 'csv').lower()
        if fmt == 'csv':
            return self._export_csv(public_rows, parsed)
        if fmt == 'xlsx':
            return self._export_xlsx(public_rows, parsed, service)
        if fmt in ('pdf', 'pdf_detail'):
            return self._export_pdf(filters, fmt)
        if fmt == 'pdf_executive':
            return self._export_pdf(filters, 'pdf_executive')
        raise UserError(_('Formato de exportación no soportado: %s') % export_format)

    @api.model
    def _filename(self, parsed, ext):
        company = parsed['company'].name.replace(' ', '_')[:30]
        d1 = fields.Date.to_string(parsed['date_from'])
        d2 = fields.Date.to_string(parsed['date_to'])
        return 'facturas_pagos_%s_%s_%s.%s' % (company, d1, d2, ext)

    @api.model
    def _export_csv(self, rows, parsed):
        output = io.StringIO()
        columns = [
            'customer', 'invoice_number', 'invoice_date', 'payment_receipt',
            'payment_date', 'days_invoice_to_payment', 'days_overdue', 'advisor',
            'bank', 'amount_untaxed', 'amount_tax', 'amount_total',
            'amount_applied', 'balance_pending', 'invoice_status', 'branch',
        ]
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        content = output.getvalue().encode('utf-8-sig')
        filename = self._filename(parsed, 'csv')
        return {
            'filename': filename,
            'mimetype': 'text/csv',
            'data': base64.b64encode(content).decode('ascii'),
        }

    @api.model
    def _export_xlsx(self, rows, parsed, service):
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_('Instale xlsxwriter para exportar Excel.'))
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        # Parameters sheet
        ws_params = workbook.add_worksheet(_('Parámetros'))
        params = service._filters_summary(parsed)
        for i, (k, v) in enumerate(params.items()):
            ws_params.write(i, 0, k)
            ws_params.write(i, 1, str(v))
        # Detail sheet
        ws = workbook.add_worksheet(_('Detalle'))
        headers = [
            _('Cliente'), _('Factura'), _('Fecha factura'), _('Recibo'),
            _('Fecha pago'), _('Días factura-pago'), _('Días atraso'), _('Asesor'),
            _('Banco'), _('Subtotal'), _('Impuesto'), _('Total'), _('Pagado'),
            _('Pendiente'), _('Estado'), _('Sucursal'),
        ]
        keys = [
            'customer', 'invoice_number', 'invoice_date', 'payment_receipt',
            'payment_date', 'days_invoice_to_payment', 'days_overdue', 'advisor',
            'bank', 'amount_untaxed', 'amount_tax', 'amount_total',
            'amount_applied', 'balance_pending', 'invoice_status', 'branch',
        ]
        money_fmt = workbook.add_format({'num_format': '#,##0.00'})
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#EEF2FF'})
        for col, h in enumerate(headers):
            ws.write(0, col, h, header_fmt)
        for row_idx, row in enumerate(rows, start=1):
            for col, key in enumerate(keys):
                val = row.get(key, '')
                if key in ('amount_untaxed', 'amount_tax', 'amount_total', 'amount_applied', 'balance_pending'):
                    ws.write_number(row_idx, col, float(val or 0), money_fmt)
                else:
                    ws.write(row_idx, col, val or '')
        ws.freeze_panes(1, 0)
        # Summary sheet
        ws_sum = workbook.add_worksheet(_('Resumen'))
        inv_map = service._unique_invoice_totals(rows)
        ws_sum.write(0, 0, _('Total facturado'))
        ws_sum.write_number(0, 1, sum(inv_map.values()), money_fmt)
        ws_sum.write(1, 0, _('Total pagado'))
        ws_sum.write_number(1, 1, sum(r.get('amount_applied', 0) for r in rows), money_fmt)
        # Aging sheet
        aging = service._build_aging(rows)
        ws_aging = workbook.add_worksheet(_('Vencimientos'))
        ws_aging.write(0, 0, _('Rango'), header_fmt)
        ws_aging.write(0, 1, _('Monto'), header_fmt)
        ws_aging.write(0, 2, _('Cantidad'), header_fmt)
        for i, (key, bucket) in enumerate(aging['buckets'].items(), start=1):
            ws_aging.write(i, 0, bucket['label'])
            ws_aging.write_number(i, 1, bucket['amount'], money_fmt)
            ws_aging.write_number(i, 2, bucket['count'])
        workbook.close()
        filename = self._filename(parsed, 'xlsx')
        return {
            'filename': filename,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'data': base64.b64encode(output.getvalue()).decode('ascii'),
        }

    @api.model
    def _export_pdf(self, filters, fmt='pdf'):
        service = self.env['gn.accounting.invoice.payment.service']
        parsed = service._parse_filters(filters)
        if fmt == 'pdf_executive':
            return self._export_pdf_executive(filters, parsed)
        wiz = self.env['gn.accounting.invoice.payment.report.wizard'].create(
            service._filters_to_wizard_vals(parsed)
        )
        report_xmlid = 'gn_accounting_reports.action_report_gn_invoice_payment'
        report = self.env.ref(report_xmlid, raise_if_not_found=True)
        pdf, _ext = self.env['ir.actions.report']._render_qweb_pdf(
            report.report_name, res_ids=wiz.ids
        )
        filename = self._filename(parsed, 'pdf')
        return {
            'filename': filename,
            'mimetype': 'application/pdf',
            'data': base64.b64encode(pdf).decode('ascii'),
        }

    @api.model
    def _export_pdf_executive(self, filters, parsed):
        import json
        Executive = self.env['gn.accounting.invoice.payment.executive.wizard']
        wiz = Executive.create({
            'company_id': parsed['company_id'],
            'filter_json': json.dumps(filters or {}),
        })
        wiz.prepare_from_filters(filters)
        report = self.env.ref(
            'gn_accounting_reports.action_report_gn_invoice_payment_executive',
            raise_if_not_found=True,
        )
        pdf, _ext = self.env['ir.actions.report']._render_qweb_pdf(
            report.report_name, res_ids=wiz.ids
        )
        filename = self._filename(parsed, 'pdf').replace('.pdf', '_ejecutivo.pdf')
        return {
            'filename': filename,
            'mimetype': 'application/pdf',
            'data': base64.b64encode(pdf).decode('ascii'),
        }