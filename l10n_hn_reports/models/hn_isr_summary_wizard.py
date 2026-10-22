# -*- coding: utf-8 -*-
import io

import xlsxwriter
from odoo import fields, models, _
from odoo.exceptions import UserError

from .hn_xlsx_utils import hn_xlsx_apply_column_widths


def _hn_isr_date_dmy(value):
    """Fecha visible XLSX ISR: dd/mm/aaaa."""
    if value is False or value is None:
        return ''
    try:
        return fields.Date.to_date(value).strftime('%d/%m/%Y')
    except (AttributeError, TypeError, ValueError):
        return str(value)


class HnIsrSummaryWizard(models.TransientModel):
    _name = 'hn.isr.summary.wizard'
    _description = 'Resumen de movimientos para control del Impuesto sobre la renta (Honduras)'

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
    account_ids = fields.Many2many(
        'account.account',
        'hn_isr_summary_wizard_account_rel',
        'wizard_id',
        'account_id',
        string='Cuentas (asistente)',
        domain="[('company_ids', 'parent_of', company_id)]",
        help='Si se deja vacío, se usan las cuentas configuradas en la compañía (Honduras — ISR).',
    )

    def _period_bounds(self):
        self.ensure_one()
        y = int(self.year)
        m = int(self.month)
        date_from = fields.Date.from_string('%s-%02d-01' % (y, m))
        date_to = fields.Date.end_of(date_from, 'month')
        return date_from, date_to

    def _resolve_accounts(self):
        self.ensure_one()
        accounts = self.account_ids
        if not accounts:
            accounts = self.company_id.hn_isr_report_account_ids
        if not accounts:
            raise UserError(_(
                'Seleccione cuentas en el asistente o configure las cuentas por defecto '
                'en la compañía (pestaña «Honduras — ISR»).'
            ))
        return accounts

    def _collect_rows(self):
        self.ensure_one()
        date_from, date_to = self._period_bounds()
        accounts = self._resolve_accounts()
        aml = self.env['account.move.line'].search([
            ('parent_state', '=', 'posted'),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('company_id', '=', self.company_id.id),
            ('account_id', 'in', accounts.ids),
            ('display_type', 'not in', ('line_section', 'line_note', 'line_subsection')),
        ], order='date asc, move_id asc, id asc')
        rows = []
        for line in aml:
            rows.append({
                'fecha': line.date,
                'asiento': line.move_id.name or '',
                'diario': line.journal_id.display_name or '',
                'cuenta': line.account_id.display_name or '',
                'contacto': line.partner_id.display_name or '',
                'etiqueta': line.name or '',
                'debe': line.debit or 0.0,
                'haber': line.credit or 0.0,
            })
        return rows, date_from, date_to, accounts

    def action_export_xlsx(self):
        self.ensure_one()
        rows, date_from, date_to, accounts = self._collect_rows()
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})
        sheet = wb.add_worksheet(_('ISR'))
        bold = wb.add_format({'bold': True})
        money = wb.add_format({'num_format': '#,##0.00'})
        cell = wb.add_format({})
        hdr = [_('Fecha'), _('Asiento'), _('Diario'), _('Cuenta'), _('Contacto'),
               _('Etiqueta'), _('Debe'), _('Haber')]
        ncols = len(hdr)
        accounts_line = (_('Cuentas: %s') % (', '.join(accounts.mapped('code'))[:500] or '—'))

        def _pad(text):
            return [text] + [''] * (ncols - 1)

        table_fit = [
            _pad(self.company_id.name or ''),
            _pad(_('Impuesto sobre la renta — resumen %s/%s') % (self.month, self.year)),
            _pad(_('%s a %s') % (_hn_isr_date_dmy(date_from), _hn_isr_date_dmy(date_to))),
            _pad(accounts_line),
            hdr,
        ]
        sheet.write(0, 0, self.company_id.name, bold)
        sheet.write(1, 0, _('Impuesto sobre la renta — resumen %s/%s') % (self.month, self.year), bold)
        sheet.write(2, 0, _('%s a %s') % (_hn_isr_date_dmy(date_from), _hn_isr_date_dmy(date_to)))
        sheet.write(3, 0, accounts_line)
        r = 5
        for c, h in enumerate(hdr):
            sheet.write(r, c, h, bold)
        r += 1
        t_debe = t_haber = 0.0
        for row in rows:
            fecha_cell = _hn_isr_date_dmy(row['fecha'])
            sheet.write(r, 0, fecha_cell, cell)
            sheet.write(r, 1, row['asiento'], cell)
            sheet.write(r, 2, row['diario'], cell)
            sheet.write(r, 3, row['cuenta'], cell)
            sheet.write(r, 4, row['contacto'], cell)
            sheet.write(r, 5, row['etiqueta'], cell)
            sheet.write_number(r, 6, float(row['debe']), money)
            sheet.write_number(r, 7, float(row['haber']), money)
            t_debe += float(row['debe'])
            t_haber += float(row['haber'])
            table_fit.append([
                fecha_cell,
                row['asiento'],
                row['diario'],
                row['cuenta'],
                row['contacto'],
                row['etiqueta'],
                float(row['debe']),
                float(row['haber']),
            ])
            r += 1
        r += 1
        sheet.write(r, 5, _('Totales'), bold)
        sheet.write_number(r, 6, t_debe, money)
        sheet.write_number(r, 7, t_haber, money)
        table_fit.append(['', '', '', '', '', _('Totales'), t_debe, t_haber])
        hn_xlsx_apply_column_widths(sheet, table_fit, max_width=85)
        wb.close()
        buf.seek(0)
        fname = 'isr_resumen_%s_%s.xlsx' % (self.year, self.month)
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
            'l10n_hn_reports.action_report_isr_summary_pdf'
        ).report_action(self)

    def action_print_html(self):
        self.ensure_one()
        return self.env.ref(
            'l10n_hn_reports.action_report_isr_summary_html'
        ).report_action(self)
