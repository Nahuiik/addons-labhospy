# -*- coding: utf-8 -*-
import io
from collections import defaultdict

import xlsxwriter
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.l10n_hn_reports.models.hn_xlsx_utils import hn_xlsx_apply_column_widths
from odoo.addons.l10n_hn_legal_books.report.legal_books_report import _format_date_dmy

from .hn_legal_book_wizard_base import DISPLAY_TYPE_EXCLUDE


class HnLibroMayorWizard(models.TransientModel):
    _name = 'hn.libro.mayor.wizard'
    _inherit = 'hn.legal.book.wizard.base'
    _description = 'Libro Mayor (Honduras)'

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wiz in self:
            if wiz.date_from and wiz.date_to and wiz.date_from > wiz.date_to:
                raise ValidationError(_('La fecha inicial no puede ser posterior a la fecha final.'))

    def _opening_domain(self):
        self.ensure_one()
        domain = [
            *self._parent_state_domain(),
            ('company_id', 'child_of', self.company_id.id),
            ('date', '<', self.date_from),
            ('display_type', 'not in', DISPLAY_TYPE_EXCLUDE),
        ]
        domain += self._journal_domain()
        return domain

    def _collect_sections(self):
        """Lista de dicts por cuenta: opening, lines (recordset), closing."""
        self.ensure_one()
        AML = self.env['account.move.line']
        Account = self.env['account.account']

        rows = AML._read_group(
            self._opening_domain(),
            ['account_id'],
            ['balance:sum'],
        )
        opening_by_account = {
            acc.id: (bal or 0.0)
            for acc, bal in rows
            if acc
        }

        period_lines = AML.search(
            self._aml_base_domain(),
            order='account_id, date asc, move_id asc, id asc',
        )
        by_account = defaultdict(list)
        for line in period_lines:
            by_account[line.account_id.id].append(line)

        acc_ids = set(opening_by_account.keys()) | set(by_account.keys())
        sections = []
        for acc_id in sorted(acc_ids, key=lambda i: Account.browse(i).code or ''):
            acc = Account.browse(acc_id)
            opening = opening_by_account.get(acc_id, 0.0)
            lines = AML.browse([l.id for l in by_account.get(acc_id, [])])
            movement_balance = sum(lines.mapped('balance'))
            closing = opening + movement_balance
            sections.append({
                'account': acc,
                'opening': opening,
                'lines': lines,
                'movement_debit': sum(lines.mapped('debit')),
                'movement_credit': sum(lines.mapped('credit')),
                'closing': closing,
            })
        return sections

    def action_export_xlsx(self):
        self.ensure_one()
        sections = self._collect_sections()
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})
        sheet = wb.add_worksheet(_('Libro Mayor'))
        bold = wb.add_format({'bold': True})
        money = wb.add_format({'num_format': '#,##0.00'})
        cell = wb.add_format({})
        hdr = [_('Fecha'), _('Asiento'), _('Diario'), _('Etiqueta'), _('Debe'), _('Haber'), _('Saldo')]
        ncols = len(hdr)

        def _empties(n):
            return [''] * n

        def _pad(text):
            return [text] + _empties(ncols - 1)

        periodo = _('%s a %s') % (
            _format_date_dmy(self.date_from),
            _format_date_dmy(self.date_to),
        )
        table_fit = [
            _pad(self.company_id.name or ''),
            _pad(_('Libro Mayor')),
            _pad(periodo),
        ]
        r = 0
        sheet.write(r, 0, self.company_id.name, bold)
        r += 1
        sheet.write(r, 0, _('Libro Mayor'), bold)
        r += 1
        sheet.write(r, 0, periodo)
        r += 2
        for sec in sections:
            acc = sec['account']
            table_fit.append([acc.code or '', acc.name or '', '', '', '', '', ''])
            table_fit.append([_('Saldo anterior'), '', '', '', '', '', float(sec['opening'])])
            table_fit.append(list(hdr))
            sheet.write(r, 0, acc.code or '', bold)
            sheet.write(r, 1, acc.name or '', bold)
            r += 1
            sheet.write(r, 0, _('Saldo anterior'), cell)
            sheet.write_number(r, 6, float(sec['opening']), money)
            r += 1
            for c, h in enumerate(hdr):
                sheet.write(r, c, h, bold)
            r += 1
            run = sec['opening']
            for line in sec['lines']:
                run += line.balance
                fecha_l = _format_date_dmy(line.date)
                sheet.write(r, 0, fecha_l, cell)
                sheet.write(r, 1, line.move_id.name or '', cell)
                sheet.write(r, 2, line.journal_id.code or '', cell)
                sheet.write(r, 3, (line.name or '')[:200], cell)
                sheet.write_number(r, 4, float(line.debit), money)
                sheet.write_number(r, 5, float(line.credit), money)
                sheet.write_number(r, 6, float(run), money)
                table_fit.append([
                    fecha_l,
                    line.move_id.name or '',
                    line.journal_id.code or '',
                    (line.name or '')[:200],
                    float(line.debit),
                    float(line.credit),
                    float(run),
                ])
                r += 1
            sheet.write(r, 3, _('Subtotal movimientos'), bold)
            sheet.write_number(r, 4, float(sec['movement_debit']), money)
            sheet.write_number(r, 5, float(sec['movement_credit']), money)
            sheet.write_number(r, 6, float(sec['closing']), money)
            table_fit.append([
                '', '', '', _('Subtotal movimientos'),
                float(sec['movement_debit']),
                float(sec['movement_credit']),
                float(sec['closing']),
            ])
            r += 2
        hn_xlsx_apply_column_widths(sheet, table_fit, max_width=85)
        wb.close()
        buf.seek(0)
        fname = 'libro_mayor_%s_%s.xlsx' % (
            _format_date_dmy(self.date_from).replace('/', '-'),
            _format_date_dmy(self.date_to).replace('/', '-'),
        )
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
            'l10n_hn_legal_books.action_report_libro_mayor_pdf',
        ).with_context(discard_logo_check=True).report_action(self, config=False)

    def action_print_html(self):
        self.ensure_one()
        return self.env.ref(
            'l10n_hn_legal_books.action_report_libro_mayor_html',
        ).with_context(discard_logo_check=True).report_action(self, config=False)
