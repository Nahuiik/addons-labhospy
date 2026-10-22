# -*- coding: utf-8 -*-
"""Motor básico declaración ISV (Form 904) por etiquetas con casilla_904."""

import io

import xlsxwriter
from odoo import api, fields, models, _
from odoo.orm.domains import Domain

from .hn_xlsx_utils import hn_xlsx_apply_column_widths


class HnIsvReport(models.TransientModel):
    _name = 'hn.isv.report'
    _description = 'Declaración ISV Honduras (904)'

    year = fields.Integer(required=True, default=lambda self: fields.Date.today().year)
    month = fields.Selection([
        ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'), ('4', 'Abril'),
        ('5', 'Mayo'), ('6', 'Junio'), ('7', 'Julio'), ('8', 'Agosto'),
        ('9', 'Septiembre'), ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre'),
    ], default=lambda self: str(fields.Date.today().month), required=True)

    @api.model
    def get_data_hn_isv(self, year=None, month=None, company=None):
        """Totales por casilla usando etiquetas con campo casilla_904.

        Las líneas de impuesto con etiqueta en reparto aportan el importe del impuesto
        (balance). La base gravada de ventas/compras (casillas 1 y 11) se toma del
        campo tax_base_amount de esas líneas de impuesto, porque en Odoo 19 las líneas
        de producto no reciben tax_repartition_line_id ni tax_tag_ids de la base.
        Casillas de bases 0 %% (2, 3, 4, 13) se completan con líneas producto que
        aplican el impuesto cuyo reparto base tiene la etiqueta correspondiente.
        """
        ctx = self.env.context
        if year is None:
            year = ctx.get('hn_isv_year', fields.Date.today().year)
        if month is None:
            month = ctx.get('hn_isv_month', fields.Date.today().month)
        comp = company or self.env.company
        y = int(year)
        m = int(month)
        date_from = fields.Date.from_string('%s-%02d-01' % (y, m))
        date_to = fields.Date.end_of(date_from, 'month')

        company_ids = comp._hn_fiscal_reports_company_ids() if comp else []
        if not company_ids:
            company_ids = [comp.id]

        Tag = self.env['account.account.tag'].sudo()
        tags = Tag.search([('casilla_904', '!=', False)])

        casillas = {}
        for tag in tags:
            casillas[tag.casilla_904] = {
                'casilla': tag.casilla_904,
                'label': tag.name or '',
                'balance': 0.0,
            }

        aml_domain_base = Domain.OR([
            Domain([
                ('date', '>=', date_from),
                ('date', '<=', date_to),
                ('parent_state', '=', 'posted'),
                ('company_id', 'in', company_ids),
            ]),
            Domain([
                ('move_id.move_type', 'in', (
                    'out_invoice', 'out_refund', 'in_invoice', 'in_refund',
                )),
                ('move_id.invoice_date', '>=', date_from),
                ('move_id.invoice_date', '<=', date_to),
                ('parent_state', '=', 'posted'),
                ('company_id', 'in', company_ids),
            ]),
        ])
        AML = self.env['account.move.line']
        Rep = self.env['account.tax.repartition.line'].sudo()

        def lines_for_tags(tag_rs):
            tag_dom = Domain([
                '|',
                ('tax_tag_ids', 'in', tag_rs.ids),
                ('tax_repartition_line_id.tag_ids', 'in', tag_rs.ids),
            ])
            return AML.sudo().search(aml_domain_base & tag_dom)

        for tag in tags:
            lines = lines_for_tags(tag)
            bal = sum(lines.mapped('balance'))
            casillas[tag.casilla_904]['balance'] += abs(bal)

        # Base imponible gravada: en Odoo 19 las líneas producto no enlazan
        # tax_repartition_line_id ni tax_tag_ids de la base; solo la línea de
        # impuesto lleva el reparto (p. ej. 904-21). La base está en tax_base_amount.
        tag21 = tags.filtered(lambda t: t.casilla_904 == 21)
        if tag21:
            tax_lines = lines_for_tags(tag21)
            if tax_lines:
                casillas[1]['balance'] = sum(
                    abs(float(x or 0.0)) for x in tax_lines.mapped('tax_base_amount')
                )
        tag31 = tags.filtered(lambda t: t.casilla_904 == 31)
        if tag31:
            tax_lines = lines_for_tags(tag31)
            if tax_lines:
                casillas[11]['balance'] = sum(
                    abs(float(x or 0.0)) for x in tax_lines.mapped('tax_base_amount')
                )

        def fill_casilla_from_product_lines(casilla_num, move_types):
            """Casillas 0 % (2/3/4/13): suma la base de las líneas producto que
            aplican el impuesto etiquetado con esa casilla 904.

            En Honduras es habitual que los impuestos ``E`` / ``EXO`` / ``EC``
            (todos al 0 %) declaren la etiqueta 904 en la línea de reparto
            ``tax``. Al ser 0 %, Odoo no genera la línea de impuesto y por eso
            no basta con buscar por ``tax_tag_ids`` en la línea contable; hay
            que resolverlo por el impuesto usado en la línea producto. La
            búsqueda acepta la etiqueta en cualquier tipo de reparto (base o
            tax) para cubrir ambas convenciones de configuración.

            Solo se consideran movimientos ``posted`` (definido en
            ``aml_domain_base``), por lo que **las facturas anuladas quedan
            excluidas** — igual que el resto del reporte.
            """
            if casilla_num not in casillas:
                return
            tag = tags.filtered(lambda t: t.casilla_904 == casilla_num)
            if not tag:
                return
            rep_lines = Rep.search([('tag_ids', 'in', tag.ids)])
            tax_ids = rep_lines.mapped('tax_id').ids
            if not tax_ids:
                return
            pl_domain = aml_domain_base & Domain([
                ('display_type', '=', 'product'),
                ('tax_ids', 'in', tax_ids),
                ('move_id.move_type', 'in', move_types),
            ])
            plines = AML.sudo().search(pl_domain)
            if plines:
                casillas[casilla_num]['balance'] = sum(
                    abs(float(b or 0.0)) for b in plines.mapped('balance')
                )

        # Exentas/exoneradas/exportaciones y compras exentas: impuesto 0 % sin línea tax útil.
        # Cubre el caso HN donde E/EXO/EC llevan la etiqueta 904 sobre la línea
        # de reparto tax (no la base) porque Odoo no genera línea de impuesto al 0 %.
        fill_casilla_from_product_lines(2, ('out_invoice', 'out_refund'))
        fill_casilla_from_product_lines(3, ('out_invoice', 'out_refund'))
        fill_casilla_from_product_lines(4, ('out_invoice', 'out_refund'))
        fill_casilla_from_product_lines(13, ('in_invoice', 'in_refund'))

        sorted_keys = sorted(casillas.keys())
        return {
            'period': {
                'year': y, 'month': m,
                'date_from': fields.Date.to_string(date_from),
                'date_to': fields.Date.to_string(date_to),
            },
            'casillas': [casillas[k] for k in sorted_keys],
            'note': _('Importes por balance contable de líneas con etiquetas 904 (validar contra SAR).'),
        }

    def action_export_xlsx(self):
        self.ensure_one()
        payload = self.get_data_hn_isv(
            year=self.year, month=int(self.month), company=self.env.company,
        )
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})
        sheet = wb.add_worksheet('904')
        bold = wb.add_format({'bold': True})
        money = wb.add_format({'num_format': '#,##0.00'})
        row = 0
        sheet.write(row, 0, self.env.company.name, bold)
        row += 1
        sheet.write(row, 0, _('Formulario 904 — %s/%s') % (payload['period']['month'], payload['period']['year']))
        row += 2
        sheet.write(row, 0, _('Casilla'), bold)
        sheet.write(row, 1, _('Descripción'), bold)
        sheet.write(row, 2, _('Importe'), bold)
        row += 1
        headers = [_('Casilla'), _('Descripción'), _('Importe')]
        subtitle = _('Formulario 904 — %s/%s') % (
            payload['period']['month'], payload['period']['year'])
        table_fit = [
            [self.env.company.name or '', '', ''],
            [subtitle, '', ''],
            headers,
        ]
        for line in payload.get('casillas', []):
            sheet.write(row, 0, line.get('casilla'))
            sheet.write(row, 1, line.get('label') or '')
            sheet.write_number(row, 2, float(line.get('balance') or 0.0), money)
            table_fit.append([
                line.get('casilla'),
                line.get('label') or '',
                float(line.get('balance') or 0.0),
            ])
            row += 1
        hn_xlsx_apply_column_widths(sheet, table_fit, max_width=85)
        wb.close()
        buf.seek(0)
        fname = 'Form_904_%s_%s.xlsx' % (self.year, self.month)
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
