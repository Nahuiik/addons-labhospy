# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, fields, models


class LabhospySalesReportXlsx(models.AbstractModel):
    _name = 'report.labhospy_sales_report.labhospy_sales_report_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Reporte ventas LabHosPy XLSX'

    def generate_xlsx_report(self, workbook, data, wizards):
        for wiz in wizards:
            self._generate_sheet(workbook, wiz)

    def _generate_sheet(self, workbook, wiz):
        sheet = workbook.add_worksheet(_('Ventas LabHosPy'))

        fmt_title = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'center',
            'valign': 'vcenter',
        })
        fmt_head = workbook.add_format({
            'bold': True,
            'bg_color': '#D9D9D9',
            'border': 1,
            'align': 'center',
            'text_wrap': True,
        })
        fmt_cell = workbook.add_format({'border': 1, 'align': 'left'})
        fmt_num = workbook.add_format({
            'border': 1,
            'align': 'right',
            'num_format': '#,##0.00',
        })
        fmt_total = workbook.add_format({
            'bold': True,
            'border': 1,
            'bg_color': '#F3F3F3',
            'align': 'right',
            'num_format': '#,##0.00',
        })

        period_list = list(wiz._iter_period_slots())
        period_keys = [p[0] for p in period_list]
        period_labels = [p[1] for p in period_list]
        n_periods = len(period_keys)
        cols_per_period = 2 if wiz.include_untaxed_value else 1

        if wiz.include_untaxed_value:
            summary_cols = 4
        else:
            summary_cols = 3
        total_cols = 8 + n_periods * cols_per_period + summary_cols

        sheet.merge_range(
            0, 0, 0, max(total_cols - 1, 1),
            _('Reporte de ventas LabHosPy'),
            fmt_title,
        )
        sheet.write(1, 0, _('Compañía: %s') % wiz.company_id.name, fmt_cell)
        sheet.write(
            2, 0,
            _('Del %s al %s') % (
                wiz.date_from.strftime('%d/%m/%Y'),
                wiz.date_to.strftime('%d/%m/%Y'),
            ),
            fmt_cell,
        )
        mode_lbl = dict(wiz._fields['group_by'].selection).get(wiz.group_by, wiz.group_by)
        sheet.write(3, 0, _('Agrupación: %s') % mode_lbl, fmt_cell)

        row = 5
        sub_row = row + 1
        col = 0
        headers = [
            _('Proveedor'),
            _('Código'),
            _('Catálogo'),
            _('Modelo'),
            _('Descripción'),
            _('Categoría'),
            _('Comercial'),
            _('Cliente'),
        ]
        for c, h in enumerate(headers):
            sheet.merge_range(row, c, sub_row, c, h, fmt_head)
        col = 8

        for _pk, plabel in zip(period_keys, period_labels):
            sheet.merge_range(
                row, col, row, col + cols_per_period - 1,
                plabel, fmt_head,
            )
            sheet.write(sub_row, col, _('Cantidad'), fmt_head)
            col += 1
            if wiz.include_untaxed_value:
                sheet.write(sub_row, col, _('Valor sin impuesto'), fmt_head)
                col += 1

        sheet.merge_range(row, col, sub_row, col, _('Cantidad total'), fmt_head)
        col += 1
        if wiz.include_untaxed_value:
            sheet.merge_range(
                row, col, sub_row, col,
                _('Valor total sin impuesto'), fmt_head,
            )
            col += 1
        sheet.merge_range(
            row, col, sub_row, col,
            _('Promedio por período'), fmt_head,
        )
        col += 1
        sheet.merge_range(
            row, col, sub_row, col,
            _('Cantidad en mano'), fmt_head,
        )

        data_row = sub_row + 1

        date_from_dt = fields.Datetime.to_datetime(wiz.date_from)
        date_to_dt = fields.Datetime.to_datetime(wiz.date_to).replace(
            hour=23, minute=59, second=59,
        )

        SaleLine = wiz.env['sale.order.line'].sudo()
        domain = [
            ('order_id.state', 'in', ('sale', 'done')),
            ('order_id.date_order', '>=', date_from_dt),
            ('order_id.date_order', '<=', date_to_dt),
            ('display_type', '=', False),
            ('order_id.company_id', '=', wiz.company_id.id),
        ]
        lines = SaleLine.search(domain)

        agg = {}
        product_ids = set()

        period_key_set = set(period_keys)

        for line in lines:
            order = line.order_id
            pk = wiz._line_period_key(order.date_order)
            if pk not in period_key_set:
                continue
            uid = order.user_id.id if order.user_id else 0
            pid = order.partner_id.id if order.partner_id else 0
            pr = line.product_id
            if not pr:
                continue
            product_ids.add(pr.id)
            gkey = (pr.id, uid, pid)

            if gkey not in agg:
                tmpl = pr.product_tmpl_id
                supplier = tmpl.gn_labhospy_supplier_id.name if tmpl.gn_labhospy_supplier_id else ''
                agg[gkey] = {
                    'supplier': supplier,
                    'code': pr.default_code or '',
                    'catalog': getattr(tmpl, 'gn_labhospy_catalog_code', '') or '',
                    'model': getattr(tmpl, 'gn_labhospy_model', '') or '',
                    'name': pr.display_name,
                    'categ': pr.categ_id.complete_name if pr.categ_id else '',
                    'user': order.user_id.name if order.user_id else '',
                    'partner': order.partner_id.name if order.partner_id else '',
                    'periods': defaultdict(lambda: {'qty': 0.0, 'untaxed': 0.0}),
                }
            cell = agg[gkey]['periods'][pk]
            cell['qty'] += line.product_uom_qty
            cell['untaxed'] += line.price_subtotal

        products = wiz.env['product.product'].sudo().browse(list(product_ids))
        qty_by_product = {p.id: p.qty_available for p in products}

        n_div = max(len(period_keys), 1)

        totals_qty_period = [0.0] * n_periods
        totals_unt_period = [0.0] * n_periods

        sorted_keys = sorted(
            agg.keys(),
            key=lambda k: (
                agg[k]['supplier'],
                agg[k]['code'],
                agg[k]['partner'],
                agg[k]['user'],
            ),
        )

        for gkey in sorted_keys:
            info = agg[gkey]
            pr_id = gkey[0]
            col = 0
            sheet.write(data_row, col, info['supplier'], fmt_cell)
            col += 1
            sheet.write(data_row, col, info['code'], fmt_cell)
            col += 1
            sheet.write(data_row, col, info['catalog'], fmt_cell)
            col += 1
            sheet.write(data_row, col, info['model'], fmt_cell)
            col += 1
            sheet.write(data_row, col, info['name'], fmt_cell)
            col += 1
            sheet.write(data_row, col, info['categ'], fmt_cell)
            col += 1
            sheet.write(data_row, col, info['user'], fmt_cell)
            col += 1
            sheet.write(data_row, col, info['partner'], fmt_cell)
            col += 1

            total_qty = 0.0
            total_untaxed = 0.0
            for i, pk in enumerate(period_keys):
                pdat = info['periods'].get(pk, {'qty': 0.0, 'untaxed': 0.0})
                q = pdat['qty']
                u = pdat['untaxed']
                total_qty += q
                total_untaxed += u
                totals_qty_period[i] += q
                totals_unt_period[i] += u
                sheet.write(data_row, col, q, fmt_num)
                col += 1
                if wiz.include_untaxed_value:
                    sheet.write(data_row, col, u, fmt_num)
                    col += 1

            avg = total_qty / n_div
            sheet.write(data_row, col, total_qty, fmt_num)
            col += 1
            if wiz.include_untaxed_value:
                sheet.write(data_row, col, total_untaxed, fmt_num)
                col += 1
            sheet.write(data_row, col, avg, fmt_num)
            col += 1
            sheet.write(data_row, col, qty_by_product.get(pr_id, 0.0), fmt_num)
            data_row += 1

        sheet.write(data_row, 0, _('Totales'), fmt_total)
        col = 8
        for i in range(n_periods):
            sheet.write(data_row, col, totals_qty_period[i], fmt_total)
            col += 1
            if wiz.include_untaxed_value:
                sheet.write(data_row, col, totals_unt_period[i], fmt_total)
                col += 1
        sheet.write(data_row, col, sum(totals_qty_period), fmt_total)
        col += 1
        if wiz.include_untaxed_value:
            sheet.write(data_row, col, sum(totals_unt_period), fmt_total)
            col += 1

        sheet.set_column(0, 0, 18)
        sheet.set_column(1, 1, 12)
        sheet.set_column(2, 3, 14)
        sheet.set_column(4, 4, 40)
        sheet.set_column(5, 7, 22)
