# -*- coding: utf-8 -*-
import io

import xlsxwriter
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.l10n_hn_reports.models.hn_xlsx_utils import hn_xlsx_apply_column_widths
from odoo.addons.l10n_hn_legal_books.report.legal_books_report import _format_date_dmy

from .hn_legal_book_wizard_base import DISPLAY_TYPE_EXCLUDE


class HnLibroInventariosBalancesWizard(models.TransientModel):
    _name = 'hn.libro.inventarios.balances.wizard'
    _inherit = 'hn.legal.book.wizard.base'
    _description = 'Libro de Inventarios y Balances (Honduras)'

    include_stock_snapshot = fields.Boolean(
        string='Incluir existencias (Stock)',
        default=True,
        help='Si el módulo Inventario está instalado, lista cantidades actuales en almacén (referencia; '
             'no sustituye inventario físico ni valuación histórica sin peritaje).',
    )
    hide_zero_balance = fields.Boolean(
        string='Ocultar cuentas con saldo cero',
        default=True,
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wiz in self:
            if wiz.date_from and wiz.date_to and wiz.date_from > wiz.date_to:
                raise ValidationError(_('La fecha inicial no puede ser posterior a la fecha final.'))

    def _balances_domain(self):
        """Saldos al cierre: movimientos hasta date_to (incl. date_from como inicio de ejercicio opcional)."""
        self.ensure_one()
        domain = [
            *self._parent_state_domain(),
            ('company_id', 'child_of', self.company_id.id),
            ('date', '<=', self.date_to),
            ('display_type', 'not in', DISPLAY_TYPE_EXCLUDE),
        ]
        domain += self._journal_domain()
        return domain

    def _collect_balance_rows(self):
        self.ensure_one()
        AML = self.env['account.move.line']
        rows = AML._read_group(
            self._balances_domain(),
            ['account_id'],
            ['debit:sum', 'credit:sum'],
        )
        rows_out = []
        for acc, debit, credit in rows:
            if not acc:
                continue
            debit_val = debit or 0.0
            credit_val = credit or 0.0
            balance_val = debit_val - credit_val
            if (
                self.hide_zero_balance
                and abs(balance_val) < 0.0001
                and debit_val < 0.0001
                and credit_val < 0.0001
            ):
                continue
            rows_out.append({
                'account': acc,
                'debit': debit_val,
                'credit': credit_val,
                'balance': balance_val,
            })
        rows_out.sort(key=lambda x: x['account'].code or '')
        return rows_out

    def _collect_stock_rows(self):
        self.ensure_one()
        if not self.include_stock_snapshot or 'stock.quant' not in self.env:
            return []
        Quant = self.env['stock.quant'].sudo()
        quants = Quant.search([
            ('company_id', 'child_of', self.company_id.id),
            ('quantity', '!=', 0.0),
        ])
        out = []
        for q in quants:
            out.append({
                'product': q.product_id.display_name,
                'default_code': q.product_id.default_code or '',
                'location': q.location_id.complete_name or q.location_id.display_name,
                'qty': q.quantity,
                'uom': q.product_uom_id.name or '',
            })
        out.sort(key=lambda x: (x['product'], x['location']))
        return out

    def action_export_xlsx(self):
        self.ensure_one()
        balance_rows = self._collect_balance_rows()
        stock_rows = self._collect_stock_rows()
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})
        bold = wb.add_format({'bold': True})
        money = wb.add_format({'num_format': '#,##0.00'})
        cell = wb.add_format({})

        bh = [_('Cuenta'), _('Nombre'), _('Debe'), _('Haber'), _('Saldo (Debe − Haber)')]
        nb = len(bh)

        def pad_b(text):
            return [text] + [''] * (nb - 1)

        subtitle_bal = _('Libro de Inventarios y Balances — Saldos al %s') % _format_date_dmy(self.date_to)
        fit_bal = [
            pad_b(self.company_id.name or ''),
            pad_b(subtitle_bal),
            bh,
        ]

        sheet_b = wb.add_worksheet(_('Balances'))
        r = 0
        sheet_b.write(r, 0, self.company_id.name, bold)
        r += 1
        sheet_b.write(r, 0, subtitle_bal, bold)
        r += 2
        for c, h in enumerate(bh):
            sheet_b.write(r, c, h, bold)
        r += 1
        td = tc = 0.0
        for row in balance_rows:
            sheet_b.write(r, 0, row['account'].code or '', cell)
            sheet_b.write(r, 1, row['account'].name or '', cell)
            sheet_b.write_number(r, 2, float(row['debit']), money)
            sheet_b.write_number(r, 3, float(row['credit']), money)
            sheet_b.write_number(r, 4, float(row['balance']), money)
            fit_bal.append([
                row['account'].code or '',
                row['account'].name or '',
                float(row['debit']),
                float(row['credit']),
                float(row['balance']),
            ])
            td += row['debit']
            tc += row['credit']
            r += 1
        r += 1
        sheet_b.write(r, 1, _('Totales'), bold)
        sheet_b.write_number(r, 2, td, money)
        sheet_b.write_number(r, 3, tc, money)
        sheet_b.write_number(r, 4, td - tc, money)
        fit_bal.append(['', _('Totales'), td, tc, td - tc])
        hn_xlsx_apply_column_widths(sheet_b, fit_bal, max_width=85)

        sheet_s = wb.add_worksheet(_('Inventarios'))
        sh = [_('Código'), _('Producto'), _('Ubicación'), _('Cantidad'), _('UdM')]
        ns = len(sh)

        def pad_s(text):
            return [text] + [''] * (ns - 1)

        title_st = _('Existencias en almacén (referencia)')
        fit_st = [
            pad_s(self.company_id.name or ''),
            pad_s(title_st),
        ]
        r = 0
        sheet_s.write(r, 0, self.company_id.name, bold)
        r += 1
        sheet_s.write(r, 0, title_st, bold)
        r += 2
        if not stock_rows:
            msg = _('Sin datos de stock o módulo Inventario no instalado.')
            sheet_s.write(r, 0, msg, cell)
            fit_st.append([msg, '', '', '', ''])
        else:
            fit_st.append(list(sh))
            for c, h in enumerate(sh):
                sheet_s.write(r, c, h, bold)
            r += 1
            for row in stock_rows:
                sheet_s.write(r, 0, row['default_code'], cell)
                sheet_s.write(r, 1, row['product'], cell)
                sheet_s.write(r, 2, row['location'], cell)
                sheet_s.write_number(r, 3, float(row['qty']), money)
                sheet_s.write(r, 4, row['uom'], cell)
                fit_st.append([
                    row['default_code'],
                    row['product'],
                    row['location'],
                    float(row['qty']),
                    row['uom'],
                ])
                r += 1
        hn_xlsx_apply_column_widths(sheet_s, fit_st, max_width=85)

        wb.close()
        buf.seek(0)
        fname = 'libro_inventarios_balances_%s.xlsx' % _format_date_dmy(self.date_to).replace('/', '-')
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
            'l10n_hn_legal_books.action_report_libro_inventarios_pdf',
        ).with_context(discard_logo_check=True).report_action(self, config=False)

    def action_print_html(self):
        self.ensure_one()
        return self.env.ref(
            'l10n_hn_legal_books.action_report_libro_inventarios_html',
        ).with_context(discard_logo_check=True).report_action(self, config=False)
