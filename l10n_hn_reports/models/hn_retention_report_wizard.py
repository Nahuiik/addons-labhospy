# -*- coding: utf-8 -*-
from odoo import _, fields, models

from .hn_xlsx_utils import hn_xlsx_apply_column_widths

# apply_field, amount_field, result_key, pct
_RETENTION_SPECS = (
    ('apply_1', 'amount_retention_1', 'retentions_1', 1.0),
    ('apply_12_5', 'amount_retention_12_5', 'retentions_12_5', 12.5),
    ('apply_15', 'amount_retention_15', 'retentions_15', 15.0),
)

_REPORT_TYPE_KEYS = {
    '1_per': 'retentions_1',
    '12_per': 'retentions_12_5',
    '15_per': 'retentions_15',
}


class HnRetentionReportWizard(models.TransientModel):
    _name = 'hn.retention.report.wizard'
    _description = 'Reporte de retenciones Honduras (Odoo 19)'

    year = fields.Integer(
        string='Año',
        required=True,
        default=lambda self: fields.Date.today().year,
    )
    month = fields.Selection(
        [
            ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'), ('4', 'Abril'),
            ('5', 'Mayo'), ('6', 'Junio'), ('7', 'Julio'), ('8', 'Agosto'),
            ('9', 'Septiembre'), ('10', 'Octubre'), ('11', 'Noviembre'),
            ('12', 'Diciembre'),
        ],
        string='Mes',
        required=True,
        default=lambda self: str(fields.Date.today().month),
    )
    report_type = fields.Selection(
        [
            ('1_per', 'Retencion 1%'),
            ('12_per', 'Retencion 12.5%'),
            ('15_per', 'Retencion 15%'),
        ],
        string='Tipo de reporte',
    )

    def _period_bounds(self):
        self.ensure_one()
        y = int(self.year)
        m = int(self.month)
        date_from = fields.Date.from_string('%s-%02d-01' % (y, m))
        date_to = fields.Date.end_of(date_from, 'month')
        return date_from, date_to

    def action_get_report(self):
        self.ensure_one()
        date_from, date_to = self._period_bounds()
        data = {
            'year': self.year,
            'month': self.month,
            'start_date': fields.Date.to_string(date_from),
            'end_date': fields.Date.to_string(date_to),
            'report_type': self.report_type,
        }
        return self.env.ref('l10n_hn_reports.action_hn_retention_report_xlsx').report_action(self, data=data)


class HnRetentionReportXlsx(models.AbstractModel):
    _name = 'report.l10n_hn_reports.hn_retention_report_xlsx'
    _description = 'Reporte de retenciones XLSX'
    _inherit = 'report.report_xlsx.abstract'

    def _fmt_date(self, value):
        return value.strftime('%d/%m/%Y') if value else ''

    def _get_payment_type_label(self, payment):
        if payment.payment_type == 'outbound':
            return 'Enviar'
        if payment.payment_type == 'inbound':
            return 'Recibir'
        if 'payment_move_type' in payment._fields and payment.payment_move_type:
            return payment.payment_move_type
        selection = dict(payment._fields.get('payment_type').selection or [])
        return selection.get(payment.payment_type, payment.payment_type or '')

    def _is_retention_applied(self, payment, apply_field):
        if apply_field not in payment._fields:
            return False
        return bool(payment[apply_field])

    def _is_pct_applied(self, payment, pct):
        pct = float(pct or 0.0)
        for apply_field, _amount_field, _result_key, spec_pct in _RETENTION_SPECS:
            if abs(spec_pct - pct) < 0.001:
                return self._is_retention_applied(payment, apply_field)
        return False

    def _is_posted_payment(self, payment):
        if payment.move_id and payment.move_id.state == 'posted':
            return True
        return payment.state in ('paid', 'in_process', 'posted')

    def _retention_amounts_for_line(self, payment, line):
        """Montos por línea de factura respetando apply_1 / apply_12_5 / apply_15."""
        amounts = {key: 0.0 for _af, _amf, key, _pct in _RETENTION_SPECS}
        for apply_field, amount_field, result_key, _pct in _RETENTION_SPECS:
            if not self._is_retention_applied(payment, apply_field):
                continue
            amounts[result_key] = float(getattr(line, amount_field, 0.0) or 0.0)
        return amounts

    def _matches_report_type(self, data, amounts):
        report_type = data.get('report_type')
        if not report_type:
            return any(amounts.values())
        key = _REPORT_TYPE_KEYS.get(report_type)
        return key and amounts.get(key, 0.0) > 0.0

    def _retention_base_amount(self, invoice):
        """Base imponible de retención: subtotal sin impuestos en moneda de la compañía."""
        if not invoice:
            return 0.0
        if invoice.currency_id == invoice.company_id.currency_id:
            return float(invoice.amount_untaxed or 0.0)
        return abs(float(invoice.amount_untaxed_signed or 0.0))

    def _build_row(self, payment, invoice, base, amounts):
        return {
            'date_payment': self._fmt_date(payment.date),
            'name_move_payment': (payment.move_id.name if payment.move_id else '') or payment.name or '',
            'type_payment': self._get_payment_type_label(payment),
            'sequence_ret': payment.retention_sequence_id if 'retention_sequence_id' in payment._fields else '',
            'name_partner': payment.partner_id.display_name or '',
            'rtn_partner': (getattr(payment.partner_id, 'rtn', False) or payment.partner_id.vat or ''),
            'journal': payment.journal_id.display_name or '',
            'invoice_name': invoice.name if invoice else '',
            'invoice_date': self._fmt_date(invoice.invoice_date if invoice else False),
            'invoice_ref': (invoice.ref if invoice else '') or '',
            'invoice_state': (invoice.state if invoice else '') or '',
            'base_retentions': base,
            'retentions_1': amounts.get('retentions_1', 0.0),
            'retentions_12_5': amounts.get('retentions_12_5', 0.0),
            'retentions_15': amounts.get('retentions_15', 0.0),
        }

    def _rows_from_invoice_lines(self, payment, data):
        rows = []
        if 'invoice_lines' not in payment._fields or not payment.invoice_lines:
            return rows
        seen = set()
        for line in payment.invoice_lines:
            invoice = getattr(line, 'invoice_id', False)
            inv_id = invoice.id if invoice else line.id
            dedup_key = (payment.id, inv_id)
            if dedup_key in seen:
                continue
            amounts = self._retention_amounts_for_line(payment, line)
            if not self._matches_report_type(data, amounts):
                continue
            seen.add(dedup_key)
            base = self._retention_base_amount(invoice)
            rows.append(self._build_row(payment, invoice, base, amounts))
        return rows

    def _retention_accounts_map(self, payment):
        AccountPayment = self.env['account.payment']
        get_param = getattr(AccountPayment, '_get_config_param', None)
        if not get_param:
            return {}
        flow = 'account_ret_' if payment.payment_type == 'outbound' else 'account_customer_ret_'
        params = self.env['ir.config_parameter'].sudo()
        result = {}
        for apply_field, _amount_field, result_key, pct in _RETENTION_SPECS:
            if not self._is_retention_applied(payment, apply_field):
                continue
            suffix = {1.0: '1', 12.5: '12_5', 15.0: '15'}[pct]
            account_id = get_param(params, flow + suffix, '')
            if not account_id:
                continue
            try:
                result[int(account_id)] = (pct, result_key)
            except (TypeError, ValueError):
                continue
        return result

    def _rows_from_write_off_lines(self, payment, data):
        rows = []
        if 'write_off_lines' not in payment._fields:
            return rows
        for wo in payment.write_off_lines:
            monto = abs(float(wo.amount or 0.0))
            pct = float(wo.amount_per or 0.0)
            if not monto and not pct:
                continue
            if not self._is_pct_applied(payment, pct):
                continue
            amounts = {key: 0.0 for _af, _amf, key, _pct in _RETENTION_SPECS}
            for _af, _amf, result_key, spec_pct in _RETENTION_SPECS:
                if abs(spec_pct - pct) < 0.001:
                    amounts[result_key] = monto
                    break
            if not self._matches_report_type(data, amounts):
                continue
            rows.append(self._build_row(payment, False, 0.0, amounts))
        return rows

    def _rows_from_payment_move(self, payment, data):
        rows = []
        move = payment.move_id
        if not move or move.state != 'posted':
            return rows
        accounts = self._retention_accounts_map(payment)
        if not accounts:
            return rows
        for line in move.line_ids:
            acc_id = line.account_id.id
            if acc_id not in accounts:
                continue
            pct, result_key = accounts[acc_id]
            monto = abs(float(line.balance or 0.0))
            if not monto:
                monto = abs(float(line.amount_currency or 0.0))
            if not monto:
                continue
            amounts = {key: 0.0 for _af, _amf, key, _pct in _RETENTION_SPECS}
            amounts[result_key] = monto
            if not self._matches_report_type(data, amounts):
                continue
            rows.append(self._build_row(payment, False, 0.0, amounts))
        return rows

    def _collect_payment_rows(self, payment, data):
        if 'invoice_lines' in payment._fields and payment.invoice_lines:
            return self._rows_from_invoice_lines(payment, data)
        rows = self._rows_from_write_off_lines(payment, data)
        if rows:
            return rows
        return self._rows_from_payment_move(payment, data)

    def _collect_rows(self, data):
        Payment = self.env['account.payment'].sudo()
        date_from = data.get('start_date')
        date_to = data.get('end_date')
        domain = [
            ('payment_type', '=', 'outbound'),
            ('company_id', '=', self.env.company.id),
        ]
        if date_from and date_to:
            domain = [
                '|',
                '&', ('date', '>=', date_from), ('date', '<=', date_to),
                '&', ('move_id.date', '>=', date_from), ('move_id.date', '<=', date_to),
            ] + domain
        elif date_from:
            domain.append(('date', '>=', date_from))
        elif date_to:
            domain.append(('date', '<=', date_to))
        if 'apply_retentions' in Payment._fields:
            domain.append(('apply_retentions', '=', True))

        rows = []
        payments = Payment.search(domain, order='date asc, id asc')
        payments = payments.filtered(self._is_posted_payment)
        payments = payments.filtered(
            lambda p: any(self._is_retention_applied(p, f) for f, *_r in _RETENTION_SPECS)
        )
        for pay in payments:
            rows.extend(self._collect_payment_rows(pay, data))
        return rows

    def generate_xlsx_report(self, workbook, data, lines):
        info = self._collect_rows(data or {})
        sheet = workbook.add_worksheet(_('Retenciones'))
        title = workbook.add_format({'font_size': 12, 'bold': True, 'align': 'center', 'border': 1})
        header = workbook.add_format({'font_size': 10, 'bold': True, 'align': 'center', 'border': 1, 'bg_color': '#000000', 'font_color': '#ffffff'})
        text = workbook.add_format({'font_size': 10, 'align': 'left', 'border': 1})
        amount = workbook.add_format({'font_size': 10, 'align': 'right', 'border': 1, 'num_format': '#,##0.00'})
        total = workbook.add_format({'font_size': 10, 'bold': True, 'align': 'right', 'border': 1, 'bg_color': '#A1EAD0', 'num_format': '#,##0.00'})

        header_labels = [
            _('No.'), _('Fecha pago'), _('Numero de pago'), _('Tipo de pago'), _('Secuencia'),
            _('Nombre proveedor'), _('RTN'), _('Diario'), _('Factura'), _('Fecha factura'),
            _('Referencia factura'), _('Estado factura'), _('Base'), _('Retencion 1%'),
            _('Retencion 12.5%'), _('Retencion 15%'), _('Total retencion'),
        ]
        ncols = len(header_labels)

        def _pad(line_text):
            return [line_text] + [''] * (ncols - 1)

        table_fit = [
            _pad(self.env.company.name or ''),
            _pad(_('Reporte de retenciones')),
        ]
        sheet.merge_range(0, 0, 0, len(header_labels) - 1, self.env.company.name or '', title)
        sheet.merge_range(1, 0, 1, len(header_labels) - 1, 'Reporte de retenciones', title)
        row = 3
        d = data or {}
        if d.get('year') is not None and d.get('month'):
            sheet.write(row, 0, _('Periodo: %s/%s') % (d['month'], d['year']), text)
        if d.get('start_date') and d.get('end_date'):
            sheet.write(row, 5, _('Del %s al %s') % (d['start_date'], d['end_date']), text)
        per_left = _('Periodo: %s/%s') % (d['month'], d['year']) if d.get('year') is not None and d.get('month') else ''
        per_right = (_('Del %s al %s') % (d['start_date'], d['end_date'])) if d.get('start_date') and d.get('end_date') else ''
        if per_left or per_right:
            prow = [''] * ncols
            prow[0] = per_left
            prow[5] = per_right
            table_fit.append(prow)
        row += 2

        for col_idx, label in enumerate(header_labels):
            sheet.write(row, col_idx, label, header)

        table_fit.append(header_labels)
        row += 1
        total_base = total_r1 = total_r12 = total_r15 = total_ret = 0.0
        for idx, rec in enumerate(info, start=1):
            line_total = rec['retentions_1'] + rec['retentions_12_5'] + rec['retentions_15']
            total_base += rec['base_retentions']
            total_r1 += rec['retentions_1']
            total_r12 += rec['retentions_12_5']
            total_r15 += rec['retentions_15']
            total_ret += line_total

            sheet.write(row, 0, idx, text)
            sheet.write(row, 1, rec['date_payment'], text)
            sheet.write(row, 2, rec['name_move_payment'], text)
            sheet.write(row, 3, rec['type_payment'], text)
            seq = rec['sequence_ret']
            seq_str = seq if isinstance(seq, str) else (seq.display_name if seq else '')
            sheet.write(row, 4, seq_str, text)
            sheet.write(row, 5, rec['name_partner'], text)
            sheet.write(row, 6, rec['rtn_partner'], text)
            sheet.write(row, 7, rec['journal'], text)
            sheet.write(row, 8, rec['invoice_name'], text)
            sheet.write(row, 9, rec['invoice_date'], text)
            sheet.write(row, 10, rec['invoice_ref'], text)
            sheet.write(row, 11, rec['invoice_state'], text)
            sheet.write_number(row, 12, rec['base_retentions'], amount)
            sheet.write_number(row, 13, rec['retentions_1'], amount)
            sheet.write_number(row, 14, rec['retentions_12_5'], amount)
            sheet.write_number(row, 15, rec['retentions_15'], amount)
            sheet.write_number(row, 16, line_total, amount)
            table_fit.append([
                idx,
                rec['date_payment'],
                rec['name_move_payment'],
                rec['type_payment'],
                seq_str,
                rec['name_partner'],
                rec['rtn_partner'],
                rec['journal'],
                rec['invoice_name'],
                rec['invoice_date'],
                rec['invoice_ref'],
                rec['invoice_state'],
                float(rec['base_retentions']),
                float(rec['retentions_1']),
                float(rec['retentions_12_5']),
                float(rec['retentions_15']),
                float(line_total),
            ])
            row += 1

        sheet.write(row, 11, _('Total general'), header)
        sheet.write_number(row, 12, total_base, total)
        sheet.write_number(row, 13, total_r1, total)
        sheet.write_number(row, 14, total_r12, total)
        sheet.write_number(row, 15, total_r15, total)
        sheet.write_number(row, 16, total_ret, total)
        table_fit.append([
            '', '', '', '', '', '', '', '', '', '', '',
            _('Total general'),
            float(total_base),
            float(total_r1),
            float(total_r12),
            float(total_r15),
            float(total_ret),
        ])
        hn_xlsx_apply_column_widths(sheet, table_fit, max_width=85, min_width=6)
