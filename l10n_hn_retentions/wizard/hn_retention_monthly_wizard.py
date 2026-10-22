# -*- coding: utf-8 -*-
import io

import xlsxwriter
from odoo import fields, models, _
from odoo.addons.l10n_hn_reports.models.hn_xlsx_utils import hn_xlsx_apply_column_widths

# apply_field, amount_field, pct, config_suffix, label
_RETENTION_SPECS = (
    ('apply_1', 'amount_retention_1', 1.0, '1', 'Retención 1%'),
    ('apply_12_5', 'amount_retention_12_5', 12.5, '12_5', 'Retención 12.5%'),
    ('apply_15', 'amount_retention_15', 15.0, '15', 'Retención 15%'),
)


class HnRetentionMonthlyWizard(models.TransientModel):
    _name = 'hn.retention.monthly.wizard'
    _description = 'Resumen de retenciones por mes (pagos publicados)'

    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    year = fields.Integer(
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
        default=lambda self: str(fields.Date.today().month),
        required=True,
    )

    def _period_bounds(self):
        self.ensure_one()
        y = int(self.year)
        m = int(self.month)
        date_from = fields.Date.from_string('%s-%02d-01' % (y, m))
        date_to = fields.Date.end_of(date_from, 'month')
        return date_from, date_to

    def _payment_type_label(self, payment):
        if payment.payment_type == 'outbound':
            return 'Enviar'
        if payment.payment_type == 'inbound':
            return 'Recibir'
        selection = dict(payment._fields['payment_type'].selection or [])
        return selection.get(payment.payment_type, payment.payment_type or '')

    def _is_retention_applied(self, payment, apply_field):
        if apply_field not in payment._fields:
            return False
        return bool(payment[apply_field])

    def _is_pct_applied(self, payment, pct):
        pct = float(pct or 0.0)
        for apply_field, _amount_field, spec_pct, _suffix, _label in _RETENTION_SPECS:
            if abs(spec_pct - pct) < 0.001:
                return self._is_retention_applied(payment, apply_field)
        return False

    def _applied_retention_specs(self, payment):
        """Solo retenciones marcadas en apply_1 / apply_12_5 / apply_15 del pago."""
        applied = []
        for apply_field, amount_field, pct, config_suffix, label in _RETENTION_SPECS:
            if not self._is_retention_applied(payment, apply_field):
                continue
            applied.append((amount_field, pct, config_suffix, label))
        return applied

    def _retention_accounts_map(self, payment):
        """Devuelve {account_id: (pct, label)} solo para retenciones aplicadas en el pago."""
        AccountPayment = self.env['account.payment']
        get_param = getattr(AccountPayment, '_get_config_param', None)
        if not get_param:
            return {}
        flow = 'account_ret_' if payment.payment_type == 'outbound' else 'account_customer_ret_'
        params = self.env['ir.config_parameter'].sudo()
        result = {}
        for _apply_field, _amount_field, pct, suffix, label in _RETENTION_SPECS:
            if not self._is_retention_applied(payment, _apply_field):
                continue
            account_id = get_param(params, flow + suffix, '')
            if not account_id:
                continue
            try:
                acc_id = int(account_id)
            except (TypeError, ValueError):
                continue
            result[acc_id] = (pct, label)
        return result

    def _row_vals(self, payment, pct, monto, cuenta, descripcion):
        return {
            'fecha': payment.date,
            'pago': payment.name or '',
            'partner': payment.partner_id.display_name or '',
            'tipo': self._payment_type_label(payment),
            'pct': pct,
            'monto': monto,
            'cuenta': cuenta,
            'descripcion': descripcion,
        }

    def _rows_from_invoice_lines(self, payment):
        """Una fila por factura y tipo de retención según payment.invoice.line."""
        rows = []
        if 'invoice_lines' not in payment._fields:
            return rows
        accounts = self._retention_accounts_map(payment)
        specs = self._applied_retention_specs(payment)
        seen = set()
        for line in payment.invoice_lines:
            invoice = getattr(line, 'invoice_id', False)
            inv_name = invoice.name if invoice else ''
            inv_id = invoice.id if invoice else line.id
            for field, pct, _config_suffix, label in specs:
                monto = float(getattr(line, field, 0.0) or 0.0)
                if monto <= 0.0:
                    continue
                dedup_key = (payment.id, inv_id, field)
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                acc_id = next(
                    (aid for aid, (p, _) in accounts.items() if p == pct),
                    False,
                )
                cuenta = self.env['account.account'].browse(acc_id).display_name if acc_id else ''
                descripcion = label
                if inv_name:
                    descripcion = 'RETENCION %s%% FC %s' % (
                        int(pct) if pct == int(pct) else pct,
                        inv_name,
                    )
                rows.append(self._row_vals(payment, pct, monto, cuenta, descripcion))
        return rows

    def _collect_payment_rows(self, payment):
        """Una sola fuente por pago; si hay líneas de factura, solo esas cuentan."""
        if 'invoice_lines' in payment._fields and payment.invoice_lines:
            return self._rows_from_invoice_lines(payment)
        rows = self._rows_from_write_off_lines(payment)
        if rows:
            return rows
        return self._rows_from_payment_move(payment)

    def _rows_from_payment_move(self, payment):
        """Retenciones contabilizadas en el asiento del pago (más fiable una vez publicado)."""
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
            pct, label = accounts[acc_id]
            if not self._is_pct_applied(payment, pct):
                continue
            monto = abs(float(line.balance or 0.0))
            if not monto:
                monto = abs(float(line.amount_currency or 0.0))
            if not monto:
                continue
            descripcion = line.name or label
            rows.append(self._row_vals(
                payment,
                pct,
                monto,
                line.account_id.display_name,
                descripcion,
            ))
        return rows

    def _rows_from_write_off_lines(self, payment):
        """Respaldo: pagos con varias retenciones vía write-off (post_diff_in=multi)."""
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
            rows.append(self._row_vals(
                payment,
                pct,
                monto,
                wo.account_id.display_name if wo.account_id else '',
                wo.description or '',
            ))
        return rows

    def _is_posted_payment(self, payment):
        if payment.move_id and payment.move_id.state == 'posted':
            return True
        return payment.state in ('paid', 'in_process', 'posted')

    def _collect_rows(self):
        self.ensure_one()
        date_from, date_to = self._period_bounds()
        Payment = self.env['account.payment'].sudo()
        domain = [
            '|',
            '&', ('date', '>=', date_from), ('date', '<=', date_to),
            '&', ('move_id.date', '>=', date_from), ('move_id.date', '<=', date_to),
            ('company_id', '=', self.company_id.id),
            ('payment_type', '=', 'outbound'),
        ]
        if 'apply_retentions' in Payment._fields:
            domain.append(('apply_retentions', '=', True))
        payments = Payment.search(domain, order='date asc, id asc')
        payments = payments.filtered(self._is_posted_payment)
        payments = payments.filtered(
            lambda p: any(self._is_retention_applied(p, f) for f, *_r in _RETENTION_SPECS)
        )
        rows = []
        for pay in payments:
            rows.extend(self._collect_payment_rows(pay))
        rows.sort(key=lambda r: (r['fecha'], r['pago'], r['pct']))
        return rows, date_from, date_to

    def action_export_xlsx(self):
        self.ensure_one()
        rows, date_from, date_to = self._collect_rows()
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})
        sheet = wb.add_worksheet(_('Retenciones'))
        bold = wb.add_format({'bold': True})
        money = wb.add_format({'num_format': '#,##0.00'})
        cell = wb.add_format({})
        hdr = [_('Fecha'), _('Pago'), _('Contacto'), _('Tipo pago'), _('%'),
               _('Monto'), _('Cuenta'), _('Descripción')]
        ncols = len(hdr)

        def _pad(text):
            return [text] + [''] * (ncols - 1)

        period_line = _('%s a %s') % (date_from, date_to)
        table_fit = [
            _pad(self.company_id.name or ''),
            _pad(_('Retenciones %s/%s') % (self.month, self.year)),
            _pad(period_line),
            hdr,
        ]
        sheet.write(0, 0, self.company_id.name, bold)
        sheet.write(1, 0, _('Retenciones %s/%s') % (self.month, self.year), bold)
        sheet.write(2, 0, period_line)
        r = 4
        for c, h in enumerate(hdr):
            sheet.write(r, c, h, bold)
        r += 1
        for row in rows:
            sheet.write(r, 0, str(row['fecha']), cell)
            sheet.write(r, 1, row['pago'], cell)
            sheet.write(r, 2, row['partner'], cell)
            sheet.write(r, 3, row['tipo'], cell)
            sheet.write_number(r, 4, float(row['pct']), money)
            sheet.write_number(r, 5, float(row['monto']), money)
            sheet.write(r, 6, row['cuenta'], cell)
            sheet.write(r, 7, row['descripcion'], cell)
            table_fit.append([
                str(row['fecha']),
                row['pago'],
                row['partner'],
                row['tipo'],
                float(row['pct']),
                float(row['monto']),
                row['cuenta'],
                row['descripcion'],
            ])
            r += 1
        hn_xlsx_apply_column_widths(sheet, table_fit, max_width=85)
        wb.close()
        buf.seek(0)
        fname = 'retenciones_%s_%s.xlsx' % (self.year, self.month)
        att = self.env['ir.attachment'].sudo().create({
            'name': fname,
            'raw': buf.read(),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % att.id,
            'target': 'self',
        }

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref(
            'l10n_hn_retentions.action_report_retention_monthly_pdf'
        ).report_action(self)

    def action_print_html(self):
        self.ensure_one()
        return self.env.ref(
            'l10n_hn_retentions.action_report_retention_monthly_html'
        ).report_action(self)
