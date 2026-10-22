# -*- coding: utf-8 -*-
"""Libro de compras / ventas (detalle facturas del período, export XLSX, QWeb PDF/HTML)."""

import io

import xlsxwriter
from odoo import api, fields, models, _
from odoo.exceptions import AccessError
from odoo.tools.misc import formatLang

from .hn_xlsx_utils import hn_xlsx_apply_column_widths
from .report_branding import company_report_branding


class HnLibroReport(models.TransientModel):
    _name = 'hn.libro.report'
    _description = 'Libro de compras o ventas (Honduras)'

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )
    tipo = fields.Selection(
        [('compras', 'Libro de compras'), ('ventas', 'Libro de ventas')],
        required=True,
        default='compras',
    )
    year = fields.Integer(required=True, default=lambda self: fields.Date.today().year)
    month = fields.Selection([
        ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'), ('4', 'Abril'),
        ('5', 'Mayo'), ('6', 'Junio'), ('7', 'Julio'), ('8', 'Agosto'),
        ('9', 'Septiembre'), ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre'),
    ], default=lambda self: str(fields.Date.today().month), required=True)
    report_layout = fields.Selection(
        [
            ('estandar', 'Detalle estándar (tabla líneas)'),
            ('resumen', 'Resumen ejecutivo'),
        ],
        required=True,
        default='estandar',
        string='Formato de impresión',
    )
    resumen_filtrar_documento_fiscal = fields.Boolean(
        string='Solo documentos con referencia fiscal (CAI / Nº proveedor)',
        default=False,
    )
    resumen_incluir_borradores_en_totales = fields.Boolean(
        string='Incluir borradores en totales del resumen',
        default=False,
    )
    branch_ids = fields.Many2many(
        'res.branch',
        'hn_libro_report_branch_rel',
        'report_id',
        'branch_id',
        string='Sucursales',
        help='Vacío = todas las sucursales de la compañía.',
    )
    user_ids = fields.Many2many(
        'res.users',
        'hn_libro_report_user_rel',
        'report_id',
        'user_id',
        string='Vendedores / responsables',
        help='Ventas: comercial de la factura. Compras: responsable de la factura. Vacío = todos.',
    )

    def _filter_labels(self):
        self.ensure_one()
        if self.branch_ids:
            branch_label = ', '.join(self.branch_ids.mapped('name'))
        else:
            branch_label = _('Todas')
        if self.user_ids:
            user_label = ', '.join(self.user_ids.mapped('name'))
        else:
            user_label = _('Todos')
        return branch_label, user_label

    def _append_filter_domain(self, domain):
        """Sucursal y vendedor/responsable sobre account.move."""
        self.ensure_one()
        Move = self.env['account.move']
        if self.branch_ids and 'branch_id' in Move._fields:
            domain.append(('branch_id', 'in', self.branch_ids.ids))
        if self.user_ids and 'invoice_user_id' in Move._fields:
            domain.append(('invoice_user_id', 'in', self.user_ids.ids))
        return domain

    def _period_bounds(self):
        self.ensure_one()
        y = int(self.year)
        m = int(self.month)
        date_from = fields.Date.from_string('%s-%02d-01' % (y, m))
        date_to = fields.Date.end_of(date_from, 'month')
        return date_from, date_to

    def _invoice_types_compras(self):
        return ('in_invoice', 'in_refund')

    def _invoice_types_ventas(self):
        return ('out_invoice', 'out_refund')

    def _move_types_tuple(self):
        self.ensure_one()
        if self.tipo == 'compras':
            return self._invoice_types_compras()
        return self._invoice_types_ventas()

    def _tipo_label(self):
        self.ensure_one()
        return dict(self._fields['tipo'].selection)[self.tipo]

    def _base_domain_lines(self, date_from, date_to, states):
        """Dominio para líneas tabulares (solo compañía del asistente)."""
        self.ensure_one()
        move_types = self._move_types_tuple()
        dom = [
            ('company_id', '=', self.company_id.id),
            ('move_type', 'in', move_types),
            ('state', 'in', list(states)),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ]
        if self.tipo == 'compras':
            dom.extend(self.env['account.move']._hn_purchase_report_exclusion_domain())
        return self._append_filter_domain(dom)

    def _line_document_vals(self, move):
        partner = move.partner_id
        cai = getattr(move, 'cai_invoice', False) or getattr(move, 'cai_shot_compras', False) or getattr(
            partner, 'cai_shot', '') or ''
        if move.move_type in ('in_invoice', 'in_refund'):
            doc = getattr(move, 'supplier_invoice_number', False) or move.name or ''
        else:
            doc = move.name or ''
        rate = move.invoice_currency_rate if getattr(move, 'invoice_currency_rate', None) else ''
        tc = rate if rate not in ('', False, None) else ''
        tax_vals = getattr(move, 'amount_tax', 0.0) or 0.0
        return {
            'fecha': fields.Date.to_string(move.invoice_date or move.date),
            'cai': cai or '',
            'rtn': partner.rtn or partner.vat or '',
            'partner': partner.name or '',
            'documento': doc,
            'base': float(move.amount_untaxed or 0.0),
            'impuesto': float(tax_vals or 0.0),
            'total': float(move.amount_total or 0.0),
            'moneda': move.currency_id.name or '',
            'tc': tc,
        }

    def _filtro_documento_fiscal(self, move):
        if move.move_type in ('in_invoice', 'in_refund'):
            sup = getattr(move, 'supplier_invoice_number', '') or ''
            return bool(move.cai_invoice or getattr(move, 'cai_shot_compras', '') or sup)
        return bool(move.cai_invoice or (move.name and move.name != '/'))

    def _fmt_money_company(self, value):
        self.ensure_one()
        cur = self.company_id.currency_id
        amt = float(value or 0.0)
        if cur:
            return formatLang(self.env, amt, currency_obj=cur)
        return formatLang(self.env, amt, grouping=True, digits=2)

    def _hn_format_date_dmy(self, value):
        """Fecha visible informes HN: día/mes/año."""
        if value is False or value is None:
            return ''
        if isinstance(value, str):
            try:
                value = fields.Date.from_string(value)
            except (ValueError, TypeError):
                return value
        try:
            return fields.Date.to_date(value).strftime('%d/%m/%Y')
        except (AttributeError, TypeError):
            return str(value)

    def _fmt_tc_company(self, tc):
        """Tipo de cambio con millares (hasta 6 decimales típico en SAR)."""
        self.ensure_one()
        if tc is None or tc is False or tc == '':
            return ''
        try:
            val = float(tc)
        except (TypeError, ValueError):
            return str(tc)
        return formatLang(self.env, val, grouping=True, digits=6)

    def _states_for_standard(self):
        return ('posted',)

    def _states_for_resumen_content(self):
        self.ensure_one()
        if self.resumen_incluir_borradores_en_totales:
            return ('draft', 'posted')
        return ('posted',)

    @api.model
    def get_data_libro(self, tipo, year, month, branch_ids=None, user_ids=None):
        """JSON para vista lista o dashboard (compañía = env.company)."""
        y = int(year)
        m = int(month)
        date_from = fields.Date.from_string('%s-%02d-01' % (y, m))
        date_to = fields.Date.end_of(date_from, 'month')
        move_types = ('in_invoice', 'in_refund') if tipo == 'compras' else ('out_invoice', 'out_refund')
        company = self.env.company
        dom = [
            ('company_id', '=', company.id),
            ('move_type', 'in', move_types),
            ('state', '=', 'posted'),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ]
        if tipo == 'compras':
            dom.extend(self.env['account.move']._hn_purchase_report_exclusion_domain())
        wiz = self.new({
            'company_id': company.id,
            'tipo': tipo,
            'year': y,
            'month': str(m),
            'branch_ids': [(6, 0, list(branch_ids or []))],
            'user_ids': [(6, 0, list(user_ids or []))],
        })
        dom = wiz._append_filter_domain(dom)
        moves = self.env['account.move'].search(dom, order='invoice_date asc, name asc')
        rows = []
        for move in moves:
            tax_vals = move.amount_tax if hasattr(move, 'amount_tax') else 0.0
            partner = move.partner_id
            cai = getattr(move, 'cai_invoice', False) or getattr(partner, 'cai_shot', '') or ''
            if move.move_type in ('in_invoice', 'in_refund'):
                doc = getattr(move, 'supplier_invoice_number', False) or move.name or ''
            else:
                doc = move.name or ''
            rows.append({
                'id': move.id,
                'fecha': fields.Date.to_string(move.invoice_date or move.date),
                'cai': cai or '',
                'rtn': partner.rtn or partner.vat or '',
                'partner': partner.name or '',
                'documento': doc,
                'base_gravada': float(move.amount_untaxed or 0.0),
                'impuesto': float(tax_vals or 0.0),
                'total': float(move.amount_total or 0.0),
                'moneda': move.currency_id.name or '',
                'tipo_cambio': move.invoice_currency_rate if move.invoice_currency_rate else '',
            })
        return {
            'period': {
                'year': y,
                'month': m,
                'date_from': fields.Date.to_string(date_from),
                'date_to': fields.Date.to_string(date_to),
            },
            'company': company.name,
            'rows': rows,
        }

    def _prepare_qweb_values_estandar(self, date_from, date_to):
        self.ensure_one()
        Move = self.env['account.move']
        moves = Move.search(
            self._base_domain_lines(date_from, date_to, self._states_for_standard()),
            order='invoice_date asc, name asc',
        )
        lines = []
        sums = {'base': 0.0, 'tax': 0.0, 'total': 0.0}
        for move in moves:
            row = dict(self._line_document_vals(move))
            row['fecha_fmt'] = self._hn_format_date_dmy(row['fecha'])
            row['base_fmt'] = self._fmt_money_company(row['base'])
            row['impuesto_fmt'] = self._fmt_money_company(row['impuesto'])
            row['total_fmt'] = self._fmt_money_company(row['total'])
            row['tc_fmt'] = self._fmt_tc_company(row['tc'])
            lines.append(row)
            sums['base'] += row['base']
            sums['tax'] += row['impuesto']
            sums['total'] += row['total']
        branding = company_report_branding(self.company_id)
        company = self.company_id
        nit = company.vat or ''
        nrc = getattr(company, 'company_registry', '') or ''
        tipo_label = self._tipo_label()
        branch_label, user_label = self._filter_labels()
        user_filter_label = _('Vendedores') if self.tipo == 'ventas' else _('Responsables')
        sums_fmt = {
            'base': self._fmt_money_company(sums['base']),
            'tax': self._fmt_money_company(sums['tax']),
            'total': self._fmt_money_company(sums['total']),
        }
        return dict(
            branding,
            company=company,
            title=_('Libro de %s') % tipo_label,
            tipo_label=tipo_label,
            date_from_fmt=self._hn_format_date_dmy(date_from),
            date_to_fmt=self._hn_format_date_dmy(date_to),
            nit=nit,
            nrc=nrc,
            branch_label=branch_label,
            user_label=user_label,
            user_filter_label=user_filter_label,
            lines=lines,
            sums=sums,
            sums_fmt=sums_fmt,
        )

    def _prepare_qweb_values_resumen(self, date_from, date_to):
        self.ensure_one()
        Move = self.env['account.move']
        states_content = self._states_for_resumen_content()
        dom_content = self._base_domain_lines(date_from, date_to, states_content)
        moves = Move.search(dom_content, order='invoice_date asc, name asc')
        if self.resumen_filtrar_documento_fiscal:
            moves = moves.filtered(self._filtro_documento_fiscal)

        dom_cancel = [
            ('company_id', '=', self.company_id.id),
            ('move_type', 'in', self._move_types_tuple()),
            ('state', '=', 'cancel'),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ]
        if self.tipo == 'compras':
            dom_cancel.extend(self.env['account.move']._hn_purchase_report_exclusion_domain())
        dom_cancel = self._append_filter_domain(dom_cancel)
        n_canceladas = Move.search_count(dom_cancel)

        n_facturas = len(moves)
        grav = moves.filtered(lambda m: abs(m.amount_tax or 0.0) >= 0.01)
        exen = moves.filtered(lambda m: abs(m.amount_tax or 0.0) < 0.01)
        total_gravado = sum(grav.mapped(lambda m: float(m.amount_total or 0.0)))
        neto_gravado = sum(grav.mapped(lambda m: float(m.amount_untaxed or 0.0)))
        monto_exentas = sum(exen.mapped(lambda m: float(m.amount_untaxed or 0.0)))
        impuestos = sum(moves.mapped(lambda m: float(m.amount_tax or 0.0)))
        total_general = sum(moves.mapped(lambda m: float(m.amount_total or 0.0)))

        mes_labels = dict(self._fields['month'].selection)
        mes_nombre = mes_labels.get(str(self.month), '')
        currency_code = self.company_id.currency_id.name or ''
        branding = company_report_branding(self.company_id)
        tipo_label = self._tipo_label()
        branch_label, user_label = self._filter_labels()
        user_filter_label = _('Vendedores') if self.tipo == 'ventas' else _('Responsables')

        sí = _('Sí')
        no = _('No')
        libro_title = tipo_label

        return dict(
            branding,
            company=self.company_id,
            hero_title=_('Resumen libro — SAR'),
            libro_title=libro_title,
            year=self.year,
            mes_nombre=mes_nombre,
            date_from_fmt=self._hn_format_date_dmy(date_from),
            date_to_fmt=self._hn_format_date_dmy(date_to),
            currency_code=currency_code,
            opt_documento_fiscal=sí if self.resumen_filtrar_documento_fiscal else no,
            opt_incluye_borradores=sí if self.resumen_incluir_borradores_en_totales else no,
            branch_label=branch_label,
            user_label=user_label,
            user_filter_label=user_filter_label,
            total_etiqueta=_('Importe total documentos (%s)') % libro_title.lower(),
            total_general_fmt=self._fmt_money_company(total_general),
            total_gravado_fmt=self._fmt_money_company(total_gravado),
            neto_gravado_fmt=self._fmt_money_company(neto_gravado),
            monto_exentas_fmt=self._fmt_money_company(monto_exentas),
            impuestos_fmt=self._fmt_money_company(impuestos),
            n_facturas=str(n_facturas),
            n_gravadas=str(len(grav)),
            n_exentas=str(len(exen)),
            n_canceladas=str(n_canceladas),
            tab_documentos_title=_('Conteo por tipo de gravamen'),
            resumen_nota_pie=_(
                'Los importes consolidan los asientos seleccionados (compañía y período). '
                'Valide contra el libro detallado y la normativa vigente antes de declarar.'
            ),
            anio_fmt_miles=formatLang(self.env, float(self.year), grouping=True, digits=0),
        )

    def _prepare_qweb_values(self, layout=None):
        self.ensure_one()
        effective = layout if layout is not None else self.report_layout
        date_from, date_to = self._period_bounds()
        if effective == 'resumen':
            return self._prepare_qweb_values_resumen(date_from, date_to)
        return self._prepare_qweb_values_estandar(date_from, date_to)

    def _libro_dashboard_check_company(self, company_id):
        cid = int(company_id)
        if cid not in self.env.user.company_ids.ids:
            raise AccessError(_('No tiene acceso a la compañía indicada para el libro.'))

    def _libro_dashboard_new_record(self, company_id, tipo, year, month, report_layout,
                                    resumen_doc_fiscal, resumen_borradores,
                                    branch_ids=None, user_ids=None):
        self._libro_dashboard_check_company(company_id)
        layout = report_layout if report_layout in ('estandar', 'resumen') else 'estandar'
        safe_tipo = 'ventas' if tipo == 'ventas' else 'compras'
        vals = {
            'company_id': int(company_id),
            'tipo': safe_tipo,
            'year': int(year),
            'month': str(int(month)),
            'report_layout': layout,
            'resumen_filtrar_documento_fiscal': bool(resumen_doc_fiscal),
            'resumen_incluir_borradores_en_totales': bool(resumen_borradores),
        }
        if branch_ids:
            vals['branch_ids'] = [(6, 0, list(branch_ids))]
        if user_ids:
            vals['user_ids'] = [(6, 0, list(user_ids))]
        return self.with_company(int(company_id)).create(vals)

    @api.model
    def get_libro_dashboard_preview(
        self,
        company_id,
        tipo,
        year,
        month,
        report_layout,
        resumen_doc_fiscal,
        resumen_borradores,
        branch_ids=None,
        user_ids=None,
    ):
        wiz = None
        try:
            wiz = self._libro_dashboard_new_record(
                company_id, tipo, year, month,
                report_layout, resumen_doc_fiscal, resumen_borradores,
                branch_ids=branch_ids, user_ids=user_ids,
            )
            date_from, date_to = wiz._period_bounds()
            branding = company_report_branding(wiz.company_id)
            company = wiz.company_id
            branch_label, user_label = wiz._filter_labels()
            user_filter_label = _('Vendedores') if wiz.tipo == 'ventas' else _('Responsables')
            payload = {
                **branding,
                'company_name': company.name or '',
                'layout': wiz.report_layout,
                'tipo_label': wiz._tipo_label(),
                'date_from': fields.Date.to_string(date_from),
                'date_to': fields.Date.to_string(date_to),
                'branch_label': branch_label,
                'user_label': user_label,
                'user_filter_label': user_filter_label,
            }
            if wiz.report_layout == 'estandar':
                qv = wiz._prepare_qweb_values_estandar(date_from, date_to)
                payload['title'] = qv['title']
                payload['nit'] = qv['nit']
                payload['nrc'] = qv['nrc']
                payload['lines'] = [{
                    'fecha': line['fecha'],
                    'cai': line['cai'],
                    'rtn': line['rtn'],
                    'partner': line['partner'],
                    'documento': line['documento'],
                    'base': line['base'],
                    'impuesto': line['impuesto'],
                    'total': line['total'],
                    'moneda': line['moneda'],
                    'tc': line['tc'],
                } for line in qv['lines']]
                payload['sums'] = qv['sums']
            else:
                qv = wiz._prepare_qweb_values_resumen(date_from, date_to)
                for key in (
                    'libro_title', 'hero_title',
                    'total_etiqueta', 'total_general_fmt', 'total_gravado_fmt',
                    'neto_gravado_fmt', 'monto_exentas_fmt', 'impuestos_fmt',
                    'n_facturas', 'n_gravadas', 'n_exentas', 'n_canceladas',
                    'opt_documento_fiscal', 'opt_incluye_borradores',
                ):
                    if key in qv:
                        payload[key] = qv[key]
            return payload
        finally:
            if wiz:
                wiz.unlink()

    @api.model
    def action_libro_dashboard_print_pdf(
        self, company_id, tipo, year, month,
        report_layout, resumen_doc_fiscal, resumen_borradores,
        branch_ids=None, user_ids=None,
    ):
        wiz = self._libro_dashboard_new_record(
            company_id, tipo, year, month,
            report_layout, resumen_doc_fiscal, resumen_borradores,
            branch_ids=branch_ids, user_ids=user_ids,
        )
        return wiz.action_print_pdf()

    @api.model
    def action_libro_dashboard_print_html(
        self, company_id, tipo, year, month,
        report_layout, resumen_doc_fiscal, resumen_borradores,
        branch_ids=None, user_ids=None,
    ):
        wiz = self._libro_dashboard_new_record(
            company_id, tipo, year, month,
            report_layout, resumen_doc_fiscal, resumen_borradores,
            branch_ids=branch_ids, user_ids=user_ids,
        )
        return wiz.action_print_html()

    @api.model
    def action_libro_dashboard_export_xlsx(
        self, company_id, tipo, year, month,
        report_layout, resumen_doc_fiscal, resumen_borradores,
        branch_ids=None, user_ids=None,
    ):
        wiz = self._libro_dashboard_new_record(
            company_id, tipo, year, month,
            report_layout, resumen_doc_fiscal, resumen_borradores,
            branch_ids=branch_ids, user_ids=user_ids,
        )
        return wiz.action_export_xlsx()

    def action_print_pdf(self):
        self.ensure_one()
        if self.report_layout == 'resumen':
            report = self.env.ref('l10n_hn_reports.action_report_hn_libro_resumen_pdf')
        else:
            report = self.env.ref('l10n_hn_reports.action_report_hn_libro_std_pdf')
        return report.report_action(self)

    def action_print_html(self):
        self.ensure_one()
        if self.report_layout == 'resumen':
            report = self.env.ref('l10n_hn_reports.action_report_hn_libro_resumen_html')
        else:
            report = self.env.ref('l10n_hn_reports.action_report_hn_libro_std_html')
        return report.report_action(self)

    def action_export_xlsx(self):
        self.ensure_one()
        date_from, date_to = self._period_bounds()
        if self.tipo == 'compras':
            move_types = self._invoice_types_compras()
            title = _('Libro de compras')
            fname = 'libro_compras_%s_%s.xlsx' % (self.year, self.month)
        else:
            move_types = self._invoice_types_ventas()
            title = _('Libro de ventas')
            fname = 'libro_ventas_%s_%s.xlsx' % (self.year, self.month)
        dom = [
            ('company_id', '=', self.company_id.id),
            ('move_type', 'in', move_types),
            ('state', '=', 'posted'),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ]
        if self.tipo == 'compras':
            dom.extend(self.env['account.move']._hn_purchase_report_exclusion_domain())
        dom = self._append_filter_domain(dom)
        moves = self.env['account.move'].search(dom, order='invoice_date asc, name asc')
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})
        sheet = wb.add_worksheet(title[:31])
        bold = wb.add_format({'bold': True})
        money = wb.add_format({'num_format': '#,##0.00'})
        rate_num = wb.add_format({'num_format': '#,##0.######'})
        headers = [_('Fecha'), _('CAI'), _('RTN'), _('Contribuyente'), _('Nº documento'),
                   _('Base'), _('ISV'), _('Total'), _('Moneda'), _('Tipo cambio')]
        ncols = len(headers)

        def _pad(text):
            return [text] + [''] * (ncols - 1)

        subtitle = '%s — %s-%s' % (title, self.year, self.month)
        table_fit = [
            _pad(self.company_id.name or ''),
            _pad(subtitle),
            headers,
        ]
        row = 0
        sheet.write(row, 0, self.company_id.name, bold)
        row += 1
        sheet.write(row, 0, subtitle)
        row += 2
        for c, h in enumerate(headers):
            sheet.write(row, c, h, bold)
        row += 1
        for move in moves:
            partner = move.partner_id
            cai = getattr(move, 'cai_invoice', False) or getattr(move, 'cai_shot_compras', '') or getattr(
                partner, 'cai_shot', '') or ''
            if move.move_type in ('in_invoice', 'in_refund'):
                doc = getattr(move, 'supplier_invoice_number', False) or move.name or ''
            else:
                doc = move.name or ''
            sheet.write(row, 0, self._hn_format_date_dmy(move.invoice_date or move.date))
            sheet.write(row, 1, cai or '')
            sheet.write(row, 2, partner.rtn or partner.vat or '')
            sheet.write(row, 3, partner.name or '')
            sheet.write(row, 4, doc or '')
            sheet.write_number(row, 5, float(move.amount_untaxed or 0.0), money)
            sheet.write_number(row, 6, float(move.amount_tax or 0.0), money)
            sheet.write_number(row, 7, float(move.amount_total or 0.0), money)
            sheet.write(row, 8, move.currency_id.name or '')
            rate = move.invoice_currency_rate if move.invoice_currency_rate else ''
            if rate != '':
                sheet.write_number(row, 9, float(rate), rate_num)
                rate_fit = float(rate)
            else:
                sheet.write(row, 9, '')
                rate_fit = ''
            table_fit.append([
                self._hn_format_date_dmy(move.invoice_date or move.date),
                cai or '',
                partner.rtn or partner.vat or '',
                partner.name or '',
                doc or '',
                float(move.amount_untaxed or 0.0),
                float(move.amount_tax or 0.0),
                float(move.amount_total or 0.0),
                move.currency_id.name or '',
                rate_fit,
            ])
            row += 1
        hn_xlsx_apply_column_widths(
            sheet,
            table_fit,
            max_width=85,
            column_float_decimals={5: 2, 6: 2, 7: 2, 9: 6},
        )
        wb.close()
        buf.seek(0)
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
