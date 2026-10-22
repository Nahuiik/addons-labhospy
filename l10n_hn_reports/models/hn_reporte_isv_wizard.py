# -*- coding: utf-8 -*-
"""Asistente «Reporte ISV» (resumen ventas / importaciones / compras y liquidación)."""
import io

import xlsxwriter
from odoo import api, fields, models, _
from odoo.tools.misc import formatLang

from .hn_xlsx_utils import hn_xlsx_apply_column_widths, hn_xlsx_str_width
from .report_branding import company_report_branding


class HnReporteIsvWizard(models.TransientModel):
    _name = 'hn.reporte.isv.wizard'
    _description = 'Reporte ISV (Honduras)'

    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        readonly=True,
    )
    year = fields.Integer(
        required=True,
        default=lambda self: fields.Date.today().year,
    )
    month = fields.Selection([
        ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'), ('4', 'Abril'),
        ('5', 'Mayo'), ('6', 'Junio'), ('7', 'Julio'), ('8', 'Agosto'),
        ('9', 'Septiembre'), ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre'),
    ], default=lambda self: str(fields.Date.today().month), required=True)
    credito_fiscal_periodo_anterior = fields.Monetary(
        string='Crédito fiscal del período anterior',
        currency_field='currency_id',
        default=0.0,
    )
    impuesto_retenido_pos = fields.Monetary(
        string='Impuesto retenido POS',
        currency_field='currency_id',
        default=0.0,
    )

    def _fmt_money(self, value):
        self.ensure_one()
        amt = float(value or 0.0)
        cur = self.currency_id
        if cur:
            return cur.format(amt)
        return formatLang(self.env, amt, grouping=True, digits=2)

    def _casilla(self, by_c, n):
        return float(by_c.get(n, 0.0) or 0.0)

    def _get_isv_resumen_data(self):
        """Totales numéricos + payload 904; único origen para QWeb y XLSX."""
        self.ensure_one()
        payload = self.env['hn.isv.report'].get_data_hn_isv(
            self.year, int(self.month), company=self.company_id,
        )
        by_c = {x['casilla']: x['balance'] for x in payload['casillas']}
        c = lambda n: self._casilla(by_c, n)

        cas1 = c(1)
        cas2 = c(2)
        cas3 = c(3)
        cas4 = c(4)
        cas11 = c(11)
        cas13 = c(13)
        cas21 = c(21)
        cas31 = c(31)

        venta_neta = cas1
        venta_gravada_15 = cas21
        ventas_exoneradas = cas2 + cas3
        ventas_export = cas4
        venta_total = cas1 + cas2 + cas3 + cas4 + cas21

        import_monto = 0.0
        import_grav_15 = 0.0
        import_total = 0.0

        compra_neta = cas11
        compra_grav_15 = cas31
        compra_exenta = cas13
        compra_total = cas11 + cas31 + cas13

        total_periodo = cas21 - cas31
        cred_ant = float(self.credito_fiscal_periodo_anterior or 0.0)
        ret_pos = float(self.impuesto_retenido_pos or 0.0)
        total_isv_pagar = total_periodo - cred_ant - ret_pos

        mes_labels = dict(self._fields['month'].selection)
        mes_nombre = mes_labels.get(str(self.month), '')

        amounts = {
            'venta_neta': venta_neta,
            'venta_gravada_15': venta_gravada_15,
            'ventas_exoneradas': ventas_exoneradas,
            'ventas_export': ventas_export,
            'venta_total': venta_total,
            'import_monto': import_monto,
            'import_grav_15': import_grav_15,
            'import_total': import_total,
            'compra_neta': compra_neta,
            'compra_grav_15': compra_grav_15,
            'compra_exenta': compra_exenta,
            'compra_total': compra_total,
            'total_periodo': total_periodo,
            'credito_fiscal_periodo_anterior': cred_ant,
            'impuesto_retenido_pos': ret_pos,
            'total_isv_pagar': total_isv_pagar,
        }
        return {
            'payload': payload,
            'mes_nombre': mes_nombre,
            'amounts': amounts,
            'show_export_row': abs(ventas_export) >= 0.01,
        }

    def _prepare_qweb_values(self):
        self.ensure_one()
        block = self._get_isv_resumen_data()
        a = block['amounts']
        mes_nombre = block['mes_nombre']
        return {
            'company': self.company_id,
            'mes_nombre': mes_nombre,
            'year': self.year,
            'periodo_linea': _('Mes: %s %s') % (mes_nombre, self.year),
            'report_title': _('Reporte ISV Ventas'),
            'venta_neta_etiqueta': _('Venta neta %s') % (self.company_id.name or '',),
            'compra_neta_etiqueta': _('Compra neta %s') % (self.company_id.name or '',),
            'venta_neta_fmt': self._fmt_money(a['venta_neta']),
            'venta_gravada_fmt': self._fmt_money(a['venta_gravada_15']),
            'ventas_exoneradas_fmt': self._fmt_money(a['ventas_exoneradas']),
            'ventas_export_fmt': self._fmt_money(a['ventas_export']),
            'venta_total_fmt': self._fmt_money(a['venta_total']),
            'import_monto_fmt': self._fmt_money(a['import_monto']),
            'import_grav_fmt': self._fmt_money(a['import_grav_15']),
            'import_total_fmt': self._fmt_money(a['import_total']),
            'compra_neta_fmt': self._fmt_money(a['compra_neta']),
            'compra_grav_fmt': self._fmt_money(a['compra_grav_15']),
            'compra_exenta_fmt': self._fmt_money(a['compra_exenta']),
            'compra_total_fmt': self._fmt_money(a['compra_total']),
            'total_a_pagar_fmt': self._fmt_money(a['total_periodo']),
            'credito_ant_fmt': self._fmt_money(a['credito_fiscal_periodo_anterior']),
            'ret_pos_fmt': self._fmt_money(a['impuesto_retenido_pos']),
            'total_isv_final_fmt': self._fmt_money(a['total_isv_pagar']),
            'show_export_row': block['show_export_row'],
        }

    def action_export_xlsx(self):
        """Hoja Resumen (alineada al PDF) + hoja Detalle 904 por casilla."""
        self.ensure_one()
        block = self._get_isv_resumen_data()
        payload = block['payload']
        a = block['amounts']
        mes_nombre = block['mes_nombre']

        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})
        bold = wb.add_format({'bold': True})
        money = wb.add_format({'num_format': '#,##0.00'})
        bold_money = wb.add_format({'bold': True, 'num_format': '#,##0.00'})
        title = wb.add_format({'bold': True, 'font_size': 12})

        sh0 = wb.add_worksheet(_('Resumen')[:31])
        meas_c0 = [
            self.company_id.name or '',
            _('Reporte ISV — resumen'),
            _('Mes: %s %s') % (mes_nombre, self.year),
        ]
        meas_c1_floats = []
        row = 0
        sh0.write(row, 0, self.company_id.name or '', title)
        row += 1
        sh0.write(row, 0, _('Reporte ISV — resumen'), bold)
        row += 1
        sh0.write(row, 0, _('Mes: %s %s') % (mes_nombre, self.year))
        row += 2

        def sec(title_str):
            nonlocal row
            meas_c0.append(title_str)
            sh0.write(row, 0, title_str, bold)
            row += 1

        def pair(label, val, value_fmt=money, label_fmt=None):
            nonlocal row
            lf = label_fmt or wb.add_format({})
            meas_c0.append(label)
            meas_c1_floats.append(float(val or 0.0))
            sh0.write(row, 0, label, lf)
            sh0.write_number(row, 1, float(val or 0.0), value_fmt)
            row += 1

        sec(_('Resumen de las ventas'))
        pair(_('Venta neta %s') % (self.company_id.name or '',), a['venta_neta'])
        pair(_('Venta gravada 15%% (débito fiscal / cas. 21)'), a['venta_gravada_15'])
        pair(_('Ventas exoneradas / exentas (cas. 2+3)'), a['ventas_exoneradas'])
        if block['show_export_row']:
            pair(_('Ventas exportación (cas. 4)'), a['ventas_export'])
        pair(_('Venta total'), a['venta_total'], bold_money, bold)

        row += 1
        sec(_('Resumen de las importaciones'))
        pair(_('Importación'), a['import_monto'])
        pair(_('Compra gravada 15%%'), a['import_grav_15'])
        pair(_('Compra total (importaciones)'), a['import_total'])

        row += 1
        sec(_('Resumen de las compras'))
        pair(_('Compra neta %s') % (self.company_id.name or '',), a['compra_neta'])
        pair(_('Compra gravada 15%% (crédito fiscal / cas. 31)'), a['compra_grav_15'])
        pair(_('Compras exentas (cas. 13)'), a['compra_exenta'])
        pair(_('Compra total'), a['compra_total'], bold_money, bold)

        row += 1
        liq_title = _('Liquidación')
        meas_c0.append(liq_title)
        sh0.write(row, 0, liq_title, bold)
        row += 1
        pair(_('Total a pagar (débito − crédito período)'), a['total_periodo'])
        pair(_('(-) Crédito fiscal período anterior'), a['credito_fiscal_periodo_anterior'])
        pair(_('(-) Impuesto retenido POS'), a['impuesto_retenido_pos'])
        pair(_('Total ISV a ser pagado'), a['total_isv_pagar'], bold_money, bold)

        w0 = max(hn_xlsx_str_width(s) for s in meas_c0) + 2
        w1 = max((hn_xlsx_str_width(f) for f in meas_c1_floats), default=14) + 2
        sh0.set_column(0, 0, min(82, max(26, w0)))
        sh0.set_column(1, 1, min(26, max(14, w1)))

        sh1 = wb.add_worksheet(_('Detalle 904')[:31])
        hdr_904 = [_('Casilla'), _('Descripción'), _('Importe')]
        table_904 = [
            [self.company_id.name or '', '', ''],
            [_('Formulario 904 — %s/%s') % (self.month, self.year), '', ''],
            hdr_904,
        ]
        sh1.write(0, 0, self.company_id.name or '', bold)
        sh1.write(1, 0, _('Formulario 904 — %s/%s') % (self.month, self.year))
        sh1.write(3, 0, _('Casilla'), bold)
        sh1.write(3, 1, _('Descripción'), bold)
        sh1.write(3, 2, _('Importe'), bold)
        r = 4
        for line in payload.get('casillas', []):
            sh1.write(r, 0, line.get('casilla'))
            sh1.write(r, 1, line.get('label') or '')
            sh1.write_number(r, 2, float(line.get('balance') or 0.0), money)
            table_904.append([
                line.get('casilla'),
                line.get('label') or '',
                float(line.get('balance') or 0.0),
            ])
            r += 1
        hn_xlsx_apply_column_widths(sh1, table_904, max_width=85)

        wb.close()
        buf.seek(0)
        fname = 'Reporte_ISV_%s_%s_%s.xlsx' % (
            self.company_id.id, self.year, self.month,
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
            'l10n_hn_reports.action_report_hn_isv_decl_pdf',
        ).with_context(discard_logo_check=True).report_action(self, config=False)

    def action_print_html(self):
        self.ensure_one()
        return self.env.ref(
            'l10n_hn_reports.action_report_hn_isv_decl_html',
        ).with_context(discard_logo_check=True).report_action(self, config=False)

    @api.model
    def _dashboard_wizard_vals(self, company_id, year, month, credito_fiscal_periodo_anterior, impuesto_retenido_pos):
        return {
            'company_id': int(company_id),
            'year': int(year),
            'month': str(int(month)),
            'credito_fiscal_periodo_anterior': float(credito_fiscal_periodo_anterior or 0),
            'impuesto_retenido_pos': float(impuesto_retenido_pos or 0),
        }

    def _build_dashboard_payload(self):
        """Estructura para el dashboard OWL (secciones + pie) alineada al PDF."""
        self.ensure_one()
        q = self._prepare_qweb_values()
        ventas_rows = [
            {'label': q['venta_neta_etiqueta'], 'value': q['venta_neta_fmt']},
            {'label': _('Venta gravada 15%'), 'value': q['venta_gravada_fmt']},
            {'label': _('Ventas exoneradas / exentas'), 'value': q['ventas_exoneradas_fmt']},
        ]
        if q['show_export_row']:
            ventas_rows.append({'label': _('Exportaciones'), 'value': q['ventas_export_fmt']})
        ventas_rows.append({'label': _('Venta total'), 'value': q['venta_total_fmt'], 'emphasis': True})

        import_rows = [
            {'label': _('Importación'), 'value': q['import_monto_fmt']},
            {'label': _('Compra gravada 15%'), 'value': q['import_grav_fmt']},
            {'spacer': True},
            {'label': _('Compra total'), 'value': q['import_total_fmt'], 'emphasis': True},
        ]
        compras_rows = [
            {'label': q['compra_neta_etiqueta'], 'value': q['compra_neta_fmt']},
            {'label': _('Compra gravada 15%'), 'value': q['compra_grav_fmt']},
            {'spacer': True},
            {'label': _('Compra total'), 'value': q['compra_total_fmt'], 'emphasis': True},
        ]
        footer_rows = [
            {'label': _('Total a pagar (débito fiscal − crédito fiscal, período)'), 'value': q['total_a_pagar_fmt']},
            {'label': _('(−) Crédito fiscal período anterior'), 'value': q['credito_ant_fmt']},
            {'label': _('(−) Impuesto retenido POS'), 'value': q['ret_pos_fmt']},
            {'label': _('Total ISV a ser pagado'), 'value': q['total_isv_final_fmt'], 'emphasis': True},
        ]
        out = {
            'title': _('Reporte ISV Ventas'),
            'company_name': self.company_id.name or '',
            'period_line': q['periodo_linea'],
            'sections': [
                {'title': _('Resumen de las ventas'), 'rows': ventas_rows},
                {'title': _('Resumen de las importaciones'), 'rows': import_rows},
                {'title': _('Resumen de las compras'), 'rows': compras_rows},
            ],
            'footer': footer_rows,
            'note': _(
                'Cifras según etiquetas del formulario 904 en el período (compañía indicada). '
                'Importaciones: valores en cero salvo criterio adicional. Solo facturas y notas '
                'de crédito registradas (posted); las anuladas quedan excluidas. '
                'Validar con contador y SAR.'
            ),
        }
        out.update(company_report_branding(self.company_id))
        return out

    @api.model
    def get_dashboard_payload(self, company_id, year, month, credito_fiscal_periodo_anterior=0.0, impuesto_retenido_pos=0.0):
        wiz = self.create(self._dashboard_wizard_vals(
            company_id, year, month, credito_fiscal_periodo_anterior, impuesto_retenido_pos,
        ))
        try:
            return wiz._build_dashboard_payload()
        finally:
            wiz.unlink()

    @api.model
    def action_dashboard_print_pdf(self, company_id, year, month, credito_fiscal_periodo_anterior=0.0, impuesto_retenido_pos=0.0):
        wiz = self.create(self._dashboard_wizard_vals(
            company_id, year, month, credito_fiscal_periodo_anterior, impuesto_retenido_pos,
        ))
        return wiz.action_print_pdf()

    @api.model
    def action_dashboard_print_html(self, company_id, year, month, credito_fiscal_periodo_anterior=0.0, impuesto_retenido_pos=0.0):
        wiz = self.create(self._dashboard_wizard_vals(
            company_id, year, month, credito_fiscal_periodo_anterior, impuesto_retenido_pos,
        ))
        return wiz.action_print_html()

    @api.model
    def action_dashboard_export_xlsx(self, company_id, year, month, credito_fiscal_periodo_anterior=0.0, impuesto_retenido_pos=0.0):
        wiz = self.create(self._dashboard_wizard_vals(
            company_id, year, month, credito_fiscal_periodo_anterior, impuesto_retenido_pos,
        ))
        return wiz.action_export_xlsx()
