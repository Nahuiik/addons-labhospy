# -*- coding: utf-8 -*-
import io

import xlsxwriter
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.l10n_hn_reports.models.hn_xlsx_utils import hn_xlsx_apply_column_widths
from odoo.addons.l10n_hn_legal_books.report.legal_books_report import _format_date_dmy


class HnLibroDiarioWizard(models.TransientModel):
    _name = 'hn.libro.diario.wizard'
    _inherit = 'hn.legal.book.wizard.base'
    _description = 'Libro Diario (Honduras)'

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wiz in self:
            if wiz.date_from and wiz.date_to and wiz.date_from > wiz.date_to:
                raise ValidationError(_('La fecha inicial no puede ser posterior a la fecha final.'))

    def _collect_rows(self):
        self.ensure_one()
        AML = self.env['account.move.line']
        lines = AML.search(
            self._aml_base_domain(),
            order='date asc, move_id asc, id asc',
        )
        cf_partner = self.env.ref(
            'gn_discount_fiscal.partner_consumidor_final',
            raise_if_not_found=False,
        )
        rows = []
        for line in lines:
            partner = line.partner_id
            contacto = partner.display_name or '' if partner else ''
            if cf_partner and partner and partner == cf_partner:
                contacto = ''
            rows.append({
                'line': line,
                'fecha': line.date,
                'asiento': line.move_id.name or '',
                'diario': line.journal_id.display_name or '',
                'ref': line.move_id.ref or '',
                'cuenta': line.account_id.display_name or '',
                'contacto': contacto,
                'etiqueta': line.name or '',
                'debe': line.debit or 0.0,
                'haber': line.credit or 0.0,
            })
        return rows

    def action_export_xlsx(self):
        self.ensure_one()
        rows = self._collect_rows()
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})
        sheet = wb.add_worksheet(_('Libro Diario'))
        bold = wb.add_format({'bold': True})
        money = wb.add_format({'num_format': '#,##0.00'})
        cell = wb.add_format({})
        hdr = [
            _('Fecha'), _('Asiento'), _('Diario'), _('Referencia'), _('Cuenta'),
            _('Contacto'), _('Etiqueta'), _('Debe'), _('Haber'),
        ]
        ncols = len(hdr)

        def _pad(text):
            return [text] + [''] * (ncols - 1)

        periodo = _('%s a %s') % (
            _format_date_dmy(self.date_from),
            _format_date_dmy(self.date_to),
        )
        table_fit = [
            _pad(self.company_id.name or ''),
            _pad(_('Libro Diario')),
            _pad(periodo),
            hdr,
        ]
        sheet.write(0, 0, self.company_id.name, bold)
        sheet.write(1, 0, _('Libro Diario'), bold)
        sheet.write(2, 0, periodo)
        r = 4
        for c, h in enumerate(hdr):
            sheet.write(r, c, h, bold)
        r += 1
        t_deb = t_cre = 0.0
        for row in rows:
            fecha_cell = _format_date_dmy(row['fecha'])
            sheet.write(r, 0, fecha_cell, cell)
            sheet.write(r, 1, row['asiento'], cell)
            sheet.write(r, 2, row['diario'], cell)
            sheet.write(r, 3, row['ref'], cell)
            sheet.write(r, 4, row['cuenta'], cell)
            sheet.write(r, 5, row['contacto'], cell)
            sheet.write(r, 6, row['etiqueta'], cell)
            sheet.write_number(r, 7, float(row['debe']), money)
            sheet.write_number(r, 8, float(row['haber']), money)
            t_deb += float(row['debe'])
            t_cre += float(row['haber'])
            table_fit.append([
                fecha_cell,
                row['asiento'],
                row['diario'],
                row['ref'],
                row['cuenta'],
                row['contacto'],
                row['etiqueta'],
                float(row['debe']),
                float(row['haber']),
            ])
            r += 1
        r += 1
        sheet.write(r, 6, _('Totales'), bold)
        sheet.write_number(r, 7, t_deb, money)
        sheet.write_number(r, 8, t_cre, money)
        table_fit.append(['', '', '', '', '', '', _('Totales'), t_deb, t_cre])
        hn_xlsx_apply_column_widths(sheet, table_fit, max_width=85)
        wb.close()
        buf.seek(0)
        fname = 'libro_diario_%s_%s.xlsx' % (
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
            'l10n_hn_legal_books.action_report_libro_diario_pdf',
        ).with_context(discard_logo_check=True).report_action(self, config=False)

    def action_print_html(self):
        self.ensure_one()
        return self.env.ref(
            'l10n_hn_legal_books.action_report_libro_diario_html',
        ).with_context(discard_logo_check=True).report_action(self, config=False)
