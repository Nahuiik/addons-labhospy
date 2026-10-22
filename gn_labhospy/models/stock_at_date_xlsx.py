# -*- coding: utf-8 -*-
import io
from datetime import datetime

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date, format_datetime

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None

_CONTEXT_KEYS = (
    'to_date',
    'warehouse',
    'warehouse_id',
    'location',
    'allowed_company_ids',
    'lang',
    'tz',
)


class ProductProductStockAtDateXlsx(models.Model):
    _inherit = 'product.product'

    def gn_labhospy_prepare_stock_at_date_context(self, raw_context):
        raw_context = raw_context or {}
        ctx = {}
        for key in _CONTEXT_KEYS:
            if key in raw_context and raw_context[key] not in (None, False, ''):
                ctx[key] = raw_context[key]
        return ctx

    def gn_labhospy_stock_at_date_xlsx(self, product_ids, raw_context=None):
        """Excel del listado Inventario a la fecha, con el mismo contexto de existencias."""
        if xlsxwriter is None:
            raise UserError(_('Falta la librería xlsxwriter para generar el Excel.'))

        ctx = self.gn_labhospy_prepare_stock_at_date_context(raw_context)
        ids = [int(pid) for pid in (product_ids or []) if pid]
        products = self.with_context(**ctx).search(
            [('id', 'in', ids), ('is_storable', '=', True)],
            order='is_favorite desc, default_code, name, id',
        )
        show_cost = (
            'avg_cost' in self._fields
            and 'total_value' in self._fields
            and self.env.user.has_group('l10n_hn_stock.group_view_costs_margins')
        )
        rows = self._gn_labhospy_stock_at_date_rows(products, ctx, show_cost)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet(_('Inventario')[:31])
        title_fmt = workbook.add_format({'bold': True, 'font_size': 14})
        meta_fmt = workbook.add_format({'italic': True, 'font_color': '#444444'})
        header_fmt = workbook.add_format({
            'bold': True,
            'bg_color': '#0B1F4B',
            'font_color': '#FFFFFF',
            'border': 1,
        })
        header_lot_fmt = workbook.add_format({
            'bold': True,
            'bg_color': '#FFE599',
            'font_color': '#000000',
            'border': 1,
        })
        text_fmt = workbook.add_format({'border': 1})
        qty_fmt = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
        money_fmt = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
        total_label_fmt = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#E8EEF7'})
        total_qty_fmt = workbook.add_format({
            'bold': True, 'border': 1, 'bg_color': '#E8EEF7', 'num_format': '#,##0.00',
        })

        to_date = ctx.get('to_date')
        if to_date:
            when = format_datetime(self.env, fields.Datetime.to_datetime(to_date))
        else:
            when = _('Actual')
        warehouses = self._gn_labhospy_warehouses_from_context(ctx)
        warehouse_label = ', '.join(warehouses.mapped('name')) or _('Todos los almacenes')

        columns = self._gn_labhospy_stock_at_date_columns(show_cost)

        sheet.write(0, 0, _('Inventario a la fecha'), title_fmt)
        sheet.write(1, 0, _('Fecha: %s') % when, meta_fmt)
        sheet.write(2, 0, _('Almacenes: %s') % warehouse_label, meta_fmt)
        sheet.write(3, 0, _('Productos: %s') % len(products), meta_fmt)

        header_row = 5
        for col, column in enumerate(columns):
            fmt = header_lot_fmt if column.get('highlight') else header_fmt
            sheet.write(header_row, col, column['header'], fmt)

        totals = {column['key']: 0.0 for column in columns if column.get('sum')}
        seen_products = set()
        for index, row in enumerate(rows, start=header_row + 1):
            product_id = row.get('product_id')
            first_of_product = product_id not in seen_products
            seen_products.add(product_id)
            for col, column in enumerate(columns):
                value = row.get(column['key'])
                kind = column['type']
                if kind == 'text':
                    sheet.write(index, col, value or '', text_fmt)
                elif value in (None, ''):
                    sheet.write(index, col, '', text_fmt)
                elif kind == 'money':
                    sheet.write_number(index, col, value or 0.0, money_fmt)
                else:
                    sheet.write_number(index, col, value or 0.0, qty_fmt)
                if column.get('sum') == 'all':
                    totals[column['key']] += value or 0.0
                elif column.get('sum') == 'product' and first_of_product:
                    totals[column['key']] += value or 0.0

        total_row = header_row + 1 + len(rows)
        for col, column in enumerate(columns):
            if col == 0:
                sheet.write(total_row, col, _('Total'), total_label_fmt)
            elif column.get('sum'):
                sheet.write_number(total_row, col, totals[column['key']], total_qty_fmt)
            else:
                sheet.write(total_row, col, '', total_label_fmt)

        for col, column in enumerate(columns):
            sheet.set_column(col, col, column['width'])
        sheet.freeze_panes(header_row + 1, 0)
        sheet.autofilter(header_row, 0, max(header_row, total_row - 1), len(columns) - 1)
        workbook.close()
        output.seek(0)

        stamp = ''
        if to_date:
            stamp = fields.Datetime.to_datetime(to_date).strftime('%Y%m%d_%H%M')
        else:
            stamp = datetime.now().strftime('%Y%m%d_%H%M')
        filename = 'inventario_a_la_fecha_%s.xlsx' % stamp
        return output.getvalue(), filename

    def _gn_labhospy_stock_at_date_columns(self, show_cost):
        columns = [
            {'key': 'location', 'header': _('Ubicación'), 'type': 'text', 'width': 24},
            {'key': 'code', 'header': _('Código'), 'type': 'text', 'width': 14},
            {'key': 'product', 'header': _('Producto'), 'type': 'text', 'width': 42},
            {'key': 'supplier', 'header': _('Proveedor'), 'type': 'text', 'width': 24},
            {'key': 'catalog', 'header': _('Código de Catálogo'), 'type': 'text', 'width': 20},
            {'key': 'model', 'header': _('Modelo'), 'type': 'text', 'width': 16},
            {'key': 'lot', 'header': _('Lote/Serie'), 'type': 'text', 'width': 18, 'highlight': True},
            {'key': 'expiration', 'header': _('Expiración'), 'type': 'text', 'width': 16, 'highlight': True},
            {'key': 'uom', 'header': _('UdM'), 'type': 'text', 'width': 14},
            {'key': 'qty', 'header': _('A la mano'), 'type': 'qty', 'width': 14, 'sum': 'all'},
        ]
        if show_cost:
            columns += [
                {'key': 'unit_cost', 'header': _('Costo Unitario'), 'type': 'money', 'width': 16},
                {'key': 'line_cost', 'header': _('Costo Total'), 'type': 'money', 'width': 16, 'sum': 'all'},
            ]
        return columns

    def _gn_labhospy_stock_at_date_rows(self, products, ctx, show_cost):
        if not products:
            return []
        fields_to_read = [
            'name',
            'default_code',
            'product_tmpl_id',
            'uom_id',
            'gn_labhospy_supplier_id',
            'gn_labhospy_catalog_code',
        ]
        if show_cost:
            fields_to_read.append('avg_cost')
        product_rows = products.with_context(**ctx).read(fields_to_read)
        by_product = {row['id']: row for row in product_rows}
        template_ids = list({row['product_tmpl_id'][0] for row in product_rows if row.get('product_tmpl_id')})
        model_by_template = {
            row['id']: row.get('gn_labhospy_model') or ''
            for row in self.env['product.template'].browse(template_ids).read(['gn_labhospy_model'])
        }
        stock_lines = self._gn_labhospy_qty_by_location_lot(products, ctx)
        location_ids = list({line['location_id'] for line in stock_lines if line['location_id']})
        lot_ids = list({line['lot_id'] for line in stock_lines if line['lot_id']})
        location_name = {
            row['id']: row['complete_name']
            for row in self.env['stock.location'].browse(location_ids).read(['complete_name'])
        }
        lot_info = {
            row['id']: row
            for row in self.env['stock.lot'].browse(lot_ids).read(['name', 'expiration_date'])
        }

        def base_row(product):
            supplier = product.get('gn_labhospy_supplier_id')
            uom = product.get('uom_id')
            template = product.get('product_tmpl_id')
            values = {
                'product_id': product['id'],
                'location': '',
                'code': product.get('default_code') or '',
                'product': product.get('name') or '',
                'catalog': product.get('gn_labhospy_catalog_code') or '',
                'model': model_by_template.get(template[0], '') if template else '',
                'lot': '',
                'expiration': '',
                'uom': uom[1] if uom else '',
                'qty': 0.0,
                'supplier': supplier[1] if supplier else '',
            }
            if show_cost:
                values['unit_cost'] = product.get('avg_cost') or 0.0
                values['line_cost'] = 0.0
            return values

        lines_by_product = {}
        for line in stock_lines:
            lines_by_product.setdefault(line['product_id'], []).append(line)

        rows = []
        for product in products:
            data = by_product.get(product.id)
            if not data:
                continue
            lines = lines_by_product.get(product.id)
            if not lines:
                rows.append(base_row(data))
                continue
            lines.sort(key=lambda item: (
                location_name.get(item['location_id'], ''),
                (lot_info.get(item['lot_id']) or {}).get('name') or '',
            ))
            for line in lines:
                row = base_row(data)
                lot = lot_info.get(line['lot_id']) or {}
                row['location'] = location_name.get(line['location_id'], '')
                row['lot'] = lot.get('name') or ''
                row['expiration'] = self._gn_labhospy_format_expiration(lot.get('expiration_date'))
                row['qty'] = line['qty']
                if show_cost:
                    row['line_cost'] = (row['unit_cost'] or 0.0) * (line['qty'] or 0.0)
                rows.append(row)
        return rows

    def _gn_labhospy_format_expiration(self, value):
        if not value:
            return ''
        moment = fields.Datetime.to_datetime(value)
        local_day = fields.Datetime.context_timestamp(self, moment).date()
        return format_date(self.env, local_day)

    def _gn_labhospy_internal_locations(self, ctx):
        warehouses = self.with_context(**ctx)._gn_labhospy_warehouses_from_context(ctx)
        if not warehouses:
            warehouses = self.env['stock.warehouse'].search([
                ('company_id', 'in', self.env.companies.ids),
            ])
        if not warehouses:
            return self.env['stock.location']
        return self.env['stock.location'].search([
            ('id', 'child_of', warehouses.mapped('view_location_id').ids),
            ('usage', '=', 'internal'),
        ])

    def _gn_labhospy_qty_by_location_lot(self, products, ctx):
        """Misma existencia que el listado: quant actual, y si la fecha es pasada se revierten los movimientos posteriores."""
        locations = self._gn_labhospy_internal_locations(ctx)
        if not products or not locations:
            return []
        to_date = ctx.get('to_date')
        moment = fields.Datetime.to_datetime(to_date) if to_date else None
        in_the_past = bool(moment and moment < fields.Datetime.now())
        companies = list(self.env.companies.ids)
        company_quant = ''
        company_move = ''
        if companies:
            company_quant = 'AND (sq.company_id IS NULL OR sq.company_id = ANY(%s))'
            company_move = 'AND (sml.company_id IS NULL OR sml.company_id = ANY(%s))'
        future = ''
        if in_the_past:
            future = """
                UNION ALL
                SELECT sml.product_id, sml.location_dest_id AS location_id,
                       sml.lot_id, -sml.quantity_product_uom AS qty
                FROM stock_move_line sml
                WHERE sml.state = 'done'
                  AND sml.product_id = ANY(%s)
                  AND sml.location_dest_id = ANY(%s)
                  AND sml.date > %s
                  {company_move}
                UNION ALL
                SELECT sml.product_id, sml.location_id,
                       sml.lot_id, sml.quantity_product_uom
                FROM stock_move_line sml
                WHERE sml.state = 'done'
                  AND sml.product_id = ANY(%s)
                  AND sml.location_id = ANY(%s)
                  AND sml.date > %s
                  {company_move}
            """.format(company_move=company_move)
        self.env.cr.execute(
            """
            SELECT product_id, location_id, lot_id, SUM(qty) AS qty
            FROM (
                SELECT sq.product_id, sq.location_id, sq.lot_id, sq.quantity AS qty
                FROM stock_quant sq
                WHERE sq.product_id = ANY(%s)
                  AND sq.location_id = ANY(%s)
                  {company_quant}
                {future}
            ) stock
            GROUP BY product_id, location_id, lot_id
            HAVING ABS(SUM(qty)) > 0.0000001
            """.format(company_quant=company_quant, future=future),
            self._gn_labhospy_qty_params(products, locations, moment if in_the_past else None, companies),
        )
        return [
            {
                'product_id': product_id,
                'location_id': location_id,
                'lot_id': lot_id,
                'qty': qty,
            }
            for product_id, location_id, lot_id, qty in self.env.cr.fetchall()
        ]

    def _gn_labhospy_qty_params(self, products, locations, moment, companies):
        product_ids = list(products.ids)
        location_ids = list(locations.ids)
        params = [product_ids, location_ids]
        if companies:
            params.append(companies)
        if moment:
            params.extend([product_ids, location_ids, moment])
            if companies:
                params.append(companies)
            params.extend([product_ids, location_ids, moment])
            if companies:
                params.append(companies)
        return params

    def _gn_labhospy_warehouses_from_context(self, ctx):
        raw = ctx.get('warehouse_id') or ctx.get('warehouse')
        if not raw:
            return self.env['stock.warehouse']
        if isinstance(raw, (list, tuple)):
            ids = [int(item) for item in raw if item]
        else:
            ids = [int(raw)]
        return self.env['stock.warehouse'].browse(ids).exists()
