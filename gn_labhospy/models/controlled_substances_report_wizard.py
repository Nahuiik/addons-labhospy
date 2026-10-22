# -*- coding: utf-8 -*-

from collections import defaultdict
from datetime import datetime, time

from odoo import _, api, fields, models
from odoo.fields import Date
from odoo.tools.misc import formatLang


class GnLabhospyControlledSubstancesReportWizard(models.TransientModel):
    _name = 'gn.labhospy.controlled.substances.report.wizard'
    _description = 'Asistente informe sustancias controladas'

    date_from = fields.Date(
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
    )
    date_to = fields.Date(required=True, default=fields.Date.context_today)
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )
    branch_ids = fields.Many2many(
        'res.branch',
        string='Sucursales',
        help='Dejar vacío para incluir todas las sucursales de la compañía.',
    )
    product_ids = fields.Many2many(
        'product.product',
        'gn_labhospy_sc_report_wiz_product_rel',
        'wizard_id',
        'product_id',
        string='Producto',
        help='Dejar vacío para incluir todas las sustancias controladas del período.',
    )

    # ------------------------------------------------------------------
    # Fechas (mismo corte que Inventario a la fecha)
    # ------------------------------------------------------------------

    def _format_sc_report_date(self, value):
        if not value:
            return ''
        if isinstance(value, str):
            d = Date.from_string(value)
        elif hasattr(value, 'date'):
            d = value.date()
        else:
            d = value
        return d.strftime('%d/%m/%Y')

    def _start_of_day_datetime(self, value):
        return datetime.combine(value, time.min)

    def _end_of_day_datetime(self, value):
        return datetime.combine(value, time.max)

    def _opening_datetime(self):
        """Corte exclusivo: existencia justo al iniciar date_from (00:00)."""
        return self._start_of_day_datetime(self.date_from)

    def _closing_datetime(self):
        """Corte inclusivo: existencia al cerrar date_to (fin del día)."""
        return self._end_of_day_datetime(self.date_to)

    # ------------------------------------------------------------------
    # Existencia = qty_available de Odoo (Inventario a la fecha)
    # ------------------------------------------------------------------

    def _branch_warehouses(self, company, branch):
        if not branch:
            return self.env['stock.warehouse']
        return self.env['stock.warehouse'].search([
            ('branch_id', '=', branch.id),
            ('company_id', '=', company.id),
        ])

    def _qty_available_context(self, company, warehouses, to_date):
        wh_ids = warehouses.ids
        return {
            'to_date': to_date,
            'warehouse_id': wh_ids[0] if len(wh_ids) == 1 else wh_ids,
            'allowed_company_ids': [company.id],
        }

    def _qty_available_at(self, company, branch, products, to_date):
        """Mapa product.id → qty_available en almacenes de la sucursal a to_date."""
        empty = {product.id: 0.0 for product in products}
        if not products or not branch:
            return empty
        warehouses = self._branch_warehouses(company, branch)
        if not warehouses:
            return empty
        products_at_date = products.with_company(company).with_context(
            **self._qty_available_context(company, warehouses, to_date)
        )
        return {product.id: product.qty_available for product in products_at_date}

    def _opening_balance(self, company, branch, product):
        """Existencia de la sucursal al inicio del período (foto Odoo)."""
        self.ensure_one()
        return self._qty_available_at(
            company, branch, product, self._opening_datetime()
        ).get(product.id, 0.0)

    def _branch_view_location_ids(self, company, branch, cache):
        """Ubicaciones que usa Existencias: hijas de view_location del almacén."""
        key = branch.id
        if key in cache:
            return cache[key]
        warehouses = self._branch_warehouses(company, branch)
        if not warehouses:
            cache[key] = set()
            return cache[key]
        locations = self.env['stock.location'].search([
            ('id', 'child_of', warehouses.mapped('view_location_id').ids),
        ])
        cache[key] = set(locations.ids)
        return cache[key]

    # ------------------------------------------------------------------
    # Movimientos del período (única fuente del libro)
    # ------------------------------------------------------------------

    def _done_stock_moves_domain(self, company):
        """Todos los move done que pueden cambiar qty_available en el período."""
        self.ensure_one()
        domain = [
            ('state', '=', 'done'),
            ('company_id', '=', company.id),
            ('product_id.product_tmpl_id.gn_labhospy_is_controlled', '=', True),
            ('date', '>', self._opening_datetime()),
            ('date', '<=', self._closing_datetime()),
        ]
        if self.product_ids:
            domain.append(('product_id', 'in', self.product_ids.ids))
        return domain

    def _stock_move_qty(self, move):
        qty = move.quantity or 0.0
        if not qty:
            return 0.0
        if move.product_uom and move.product_id.uom_id and move.product_uom != move.product_id.uom_id:
            qty = move.product_uom._compute_quantity(qty, move.product_id.uom_id)
        return move.product_id.uom_id.round(qty)

    def _stock_move_qty_delta(self, move, branch_loc_ids):
        """Mismo criterio in/out que qty_available: cruza el perímetro del almacén."""
        if not branch_loc_ids:
            return 0.0
        qty = self._stock_move_qty(move)
        if not qty:
            return 0.0
        src_in = move.location_id.id in branch_loc_ids
        dest_in = move.location_dest_id.id in branch_loc_ids
        if src_in and not dest_in:
            return move.product_id.uom_id.round(-qty)
        if dest_in and not src_in:
            return qty
        return 0.0

    def _inter_store_transfer_by_picking_id(self, picking_ids):
        """Mapa picking_id → traslado entre tiendas (si el módulo está instalado)."""
        if not picking_ids or 'stock.inter.store.transfer' not in self.env:
            return {}
        transfers = self.env['stock.inter.store.transfer'].search([
            '|',
            ('picking_out_id', 'in', picking_ids),
            ('picking_in_id', 'in', picking_ids),
        ])
        result = {}
        for transfer in transfers:
            if transfer.picking_out_id:
                result[transfer.picking_out_id.id] = transfer
            if transfer.picking_in_id:
                result[transfer.picking_in_id.id] = transfer
        return result

    # ------------------------------------------------------------------
    # Clasificación y datos legales (encima del movimiento)
    # ------------------------------------------------------------------

    def _location_branch(self, location):
        if not location:
            return self.env['res.branch']
        if location.branch_id:
            return location.branch_id
        warehouse = location.warehouse_id
        if warehouse and warehouse.branch_id:
            return warehouse.branch_id
        return self.env['res.branch']

    def _stock_move_kind(self, move):
        src = move.location_id.usage
        dest = move.location_dest_id.usage
        if move.scrap_id or dest == 'inventory' and not move.is_inventory:
            if src == 'internal' or dest != 'internal':
                return 'scrap'
        if move.is_inventory or src == 'inventory' or dest == 'inventory':
            return 'inventory'
        if dest == 'customer':
            return 'delivery'
        if src == 'customer':
            return 'customer_return'
        if src == 'supplier':
            return 'receipt'
        if dest == 'supplier':
            return 'purchase_return'
        if src == 'production' or dest == 'production':
            return 'production'
        return 'transfer'

    def _transaction_label(self, kind, branch):
        labels = {
            'delivery': _('Entrega a Clientes'),
            'customer_return': _('Devolución de clientes'),
            'receipt': _('Recepción'),
            'purchase_return': _('Devolución a proveedor'),
            'inventory': _('Ajuste de inventario'),
            'scrap': _('Merma'),
            'production': _('Producción'),
            'transfer': _('Traslados'),
        }
        label = labels.get(kind, _('Movimiento'))
        if kind == 'delivery' and branch and branch.name:
            return '%s %s' % (label, branch.name)
        return label

    def _transfer_direction_display(self, move):
        src_label = self._location_branch(move.location_id).name or move.location_id.display_name
        dest_label = self._location_branch(move.location_dest_id).name or move.location_dest_id.display_name
        return '%s -> %s' % (src_label, dest_label)

    def _stock_move_lot_display(self, move):
        lot_names = []
        for ml in move.move_line_ids:
            if ml.lot_id and ml.lot_id.name and ml.lot_id.name not in lot_names:
                lot_names.append(ml.lot_id.name)
        return ', '.join(lot_names)

    def _stock_move_sale_line(self, move):
        return move.sale_line_id or move.origin_returned_move_id.sale_line_id

    def _sale_line_posted_invoice_lines(self, sale_line, product):
        if not sale_line:
            return self.env['account.move.line']
        lines = sale_line.invoice_lines.filtered(
            lambda aml: aml.display_type == 'product'
            and aml.move_id.state == 'posted'
            and aml.move_id.move_type in ('out_invoice', 'out_refund')
        )
        same_product = lines.filtered(lambda aml: aml.product_id == product)
        return same_product or lines

    def _invoice_line_sale_line(self, aml):
        return aml.sale_line_ids[:1]

    def _invoice_line_application_use_display(self, aml):
        line = aml
        sale_line = self._invoice_line_sale_line(aml)
        if line.display_type != 'product' or not line.product_id:
            return ''
        if line.gn_labhospy_application_use_id:
            name = (line.gn_labhospy_application_use_id.name or '').strip()
            if name:
                return name
        line_use = (line.gn_labhospy_application_use or '').strip()
        if line_use:
            return line_use
        if sale_line:
            return self._sale_line_application_use_display(sale_line)
        tmpl_use = line.product_id.product_tmpl_id.gn_labhospy_application_use_id
        if tmpl_use:
            return (tmpl_use.name or '').strip()
        return ''

    def _sale_line_application_use_display(self, sale_line):
        if not sale_line:
            return ''
        if sale_line.gn_labhospy_application_use_id:
            name = (sale_line.gn_labhospy_application_use_id.name or '').strip()
            if name:
                return name
        return (sale_line.gn_labhospy_application_use or '').strip()

    def _empresa_contacto_display(self, empresa, contacto):
        empresa = (empresa or '').strip()
        contacto = (contacto or '').strip()
        if empresa and contacto:
            return '%s\n%s' % (empresa, contacto)
        return empresa or contacto

    def _partner_address_display(self, partner):
        if not partner:
            return ''
        return (partner._display_address(without_company=True) or '').replace('\n', ', ').strip()

    def _legal_parts_from_invoice(self, aml):
        invoice = aml.move_id.ensure_one()
        return {
            'empresa': invoice.commercial_partner_id.display_name or '',
            'contacto': invoice._gn_labhospy_sc_report_contact_name(),
            'direccion': invoice._gn_labhospy_sc_report_partner_address(),
            'aplicacion_uso': self._invoice_line_application_use_display(aml),
            'documento': invoice.name or '',
        }

    def _legal_parts_from_partner(self, partner, aplicacion_uso=''):
        if not partner:
            return {
                'empresa': '',
                'contacto': '',
                'direccion': '',
                'aplicacion_uso': aplicacion_uso,
                'documento': '',
            }
        comm = partner.commercial_partner_id
        contacto = ''
        if partner != comm and not partner.is_company:
            contacto = (partner.name or '').strip()
        elif not comm.is_company:
            contacto = (comm.name or '').strip()
        return {
            'empresa': comm.display_name or '',
            'contacto': contacto,
            'direccion': self._partner_address_display(partner),
            'aplicacion_uso': aplicacion_uso,
            'documento': '',
        }

    def _stock_move_resolution(self, move):
        picking = move.picking_id
        if picking and (picking.gn_labhospy_resolution_ref or '').strip():
            return picking.gn_labhospy_resolution_ref.strip()
        names = []
        for ml in move.move_line_ids:
            ref = (ml.gn_labhospy_arsa_resolution_no or '').strip()
            if ref and ref not in names:
                names.append(ref)
        return ', '.join(names)

    def _stock_move_document_display(self, move, kind, invoice_names, transfer_by_picking=None):
        if invoice_names:
            return ', '.join(invoice_names)
        picking = move.picking_id
        if kind == 'transfer' and picking and transfer_by_picking:
            transfer = transfer_by_picking.get(picking.id)
            if transfer and transfer.hn_remission_number:
                return transfer.hn_remission_number
        if picking and getattr(picking, 'hn_remission_number', None):
            return picking.hn_remission_number
        if move.scrap_id:
            return move.scrap_id.name or ''
        return (picking.name if picking else move.reference) or ''

    def _legal_parts_for_move(self, move, kind):
        move = move.sudo()
        sale_line = self._stock_move_sale_line(move)
        invoice_lines = self._sale_line_posted_invoice_lines(sale_line, move.product_id)
        invoice_names = []
        if invoice_lines:
            parts = None
            for aml in invoice_lines:
                name = (aml.move_id.name or '').strip()
                if name and name not in invoice_names:
                    invoice_names.append(name)
                if parts is None:
                    parts = self._legal_parts_from_invoice(aml)
            if parts:
                parts['documento'] = ', '.join(invoice_names)
                return parts, invoice_names

        aplicacion = self._sale_line_application_use_display(sale_line)
        if sale_line:
            order = sale_line.order_id
            partner = order.partner_invoice_id or order.partner_id
            parts = self._legal_parts_from_partner(partner, aplicacion)
            return parts, invoice_names

        if kind in ('receipt', 'purchase_return'):
            purchase = move.purchase_line_id.order_id if move.purchase_line_id else False
            partner = (purchase.partner_id if purchase else False) or move.picking_id.partner_id
            return self._legal_parts_from_partner(partner), invoice_names

        if kind in ('delivery', 'customer_return') and move.picking_id.partner_id:
            return self._legal_parts_from_partner(move.picking_id.partner_id, aplicacion), invoice_names

        return {
            'empresa': '',
            'contacto': '',
            'direccion': '',
            'aplicacion_uso': aplicacion,
            'documento': '',
        }, invoice_names

    def _qty_cell(self, value):
        if not value:
            return ''
        return value

    def _ledger_row_from_stock_move(self, move, branch, delta, transfer_by_picking=None):
        move_dt = fields.Datetime.to_datetime(move.date) if move.date else self._opening_datetime()
        move_date = move_dt.date()
        kind = self._stock_move_kind(move)
        legal, invoice_names = self._legal_parts_for_move(move, kind)
        if kind == 'transfer' and not legal['direccion']:
            legal['direccion'] = self._transfer_direction_display(move)
        elif kind in ('inventory', 'scrap', 'production') and not legal['direccion']:
            legal['direccion'] = self._transfer_direction_display(move)

        if delta < 0:
            ingreso_cell = ''
            salida_cell = self._qty_cell(delta)
        else:
            ingreso_cell = self._qty_cell(delta)
            salida_cell = ''

        return {
            'sort_date': move_dt,
            'sort_id': move.id,
            'delta': delta,
            'row': {
                'fecha_str': self._format_sc_report_date(move_date),
                'empresa_contacto': self._empresa_contacto_display(
                    legal['empresa'], legal['contacto']
                ),
                'direccion': legal['direccion'],
                'aplicacion_uso': legal['aplicacion_uso'],
                'transaccion': self._transaction_label(kind, branch),
                'resolucion': self._stock_move_resolution(move),
                'documento': self._stock_move_document_display(
                    move, kind, invoice_names, transfer_by_picking=transfer_by_picking
                ),
                'lote': self._stock_move_lot_display(move),
                'ingreso': ingreso_cell,
                'salida': salida_cell,
                'saldo': '',
                'es_saldo_inicial': False,
            },
        }

    def _rows_with_running_balance(self, opening_balance, ledger_entries):
        rows = [{
            'fecha_str': self._format_sc_report_date(self.date_from),
            'empresa_contacto': '',
            'direccion': '',
            'aplicacion_uso': '',
            'transaccion': _('Saldo inicial'),
            'resolucion': '',
            'documento': '',
            'lote': '',
            'ingreso': '',
            'salida': '',
            'saldo': opening_balance,
            'es_saldo_inicial': True,
        }]
        running = opening_balance
        for entry in ledger_entries:
            running += entry['delta']
            row = entry['row']
            row['saldo'] = running
            rows.append(row)
        return rows

    # ------------------------------------------------------------------
    # Armado de páginas
    # ------------------------------------------------------------------

    def _branch_report_header(self, branch, company):
        address = (branch.address or '').replace('\n', ', ') if branch else ''
        return {
            'branch': branch,
            'branch_name': branch.name if branch else '',
            'establishment_name': company.name,
            'license_no': (branch.gn_labhospy_sanitary_license_no or '').strip() if branch else '',
            'phone': (branch.telephone_no or '').strip() if branch else '',
            'address': address,
        }

    def _product_section_header(self, product):
        tmpl = product.product_tmpl_id
        code = (tmpl.default_code or '').strip()
        catalog = (tmpl.gn_labhospy_catalog_code or '').strip()
        name = (tmpl.gn_labhospy_sc_presentation or tmpl.name or '').strip()
        return {
            'hdr_code': code,
            'hdr_name': name,
            'hdr_catalog': catalog,
            'catalog_label': _('Catálogo'),
        }

    def _report_branches(self, company):
        if self.branch_ids:
            return self.branch_ids
        return self.env['res.branch'].search([('company_id', '=', company.id)])

    def _controlled_products(self, _company):
        if self.product_ids:
            return self.product_ids
        return self.env['product.product'].search([
            ('product_tmpl_id.gn_labhospy_is_controlled', '=', True),
        ])

    def _build_ledger_sections(self):
        """Una página por sucursal y producto: foto inicial + movimientos de stock."""
        self.ensure_one()
        company = self.company_id
        Branch = self.env['res.branch']
        Product = self.env['product.product']
        branches = self._report_branches(company)
        loc_cache = {}

        period_moves = self.env['stock.move'].search(
            self._done_stock_moves_domain(company),
            order='date, id',
        )
        # Datos legales (pedido/factura/compra) pueden ser de otro vendedor o sucursal.
        # El menú lo abre group_sale_salesman («solo documentos propios»); sin sudo el
        # prefetch de sale_line_id.order_id dispara AccessError y el 403 del HTML.
        if period_moves:
            period_moves = period_moves.sudo()
            period_moves.mapped('move_line_ids.lot_id')
            period_moves.mapped('sale_line_id.invoice_lines.move_id')
            period_moves.mapped('origin_returned_move_id.sale_line_id')
            period_moves.mapped('purchase_line_id.order_id')
            period_moves.mapped('picking_id')
            period_moves.mapped('scrap_id')

        transfer_by_picking = self._inter_store_transfer_by_picking_id(
            period_moves.mapped('picking_id').ids
        )

        ledger_by_key = defaultdict(list)
        for move in period_moves:
            for branch in branches:
                loc_ids = self._branch_view_location_ids(company, branch, loc_cache)
                delta = self._stock_move_qty_delta(move, loc_ids)
                if not delta:
                    continue
                key = (branch.id, move.product_id.id)
                ledger_by_key[key].append(
                    self._ledger_row_from_stock_move(
                        move, branch, delta, transfer_by_picking=transfer_by_picking
                    )
                )

        products = self._controlled_products(company)
        if not self.product_ids:
            moved_ids = {move.product_id.id for move in period_moves}
            products = Product.browse(list(set(products.ids) | moved_ids))

        opening_by_key = {}
        keys = set(ledger_by_key)
        for branch in branches:
            opening_map = self._qty_available_at(
                company, branch, products, self._opening_datetime()
            )
            for product in products:
                if not product.product_tmpl_id.gn_labhospy_is_controlled:
                    continue
                key = (branch.id, product.id)
                opening = opening_map.get(product.id, 0.0)
                opening_by_key[key] = opening
                if key in keys or opening:
                    keys.add(key)

        pages = []
        branch_product_keys = sorted(
            keys,
            key=lambda key: (
                (Branch.browse(key[0]).name or '').lower() if key[0] else '',
                Product.browse(key[1]).display_name.lower(),
            ),
        )

        for branch_id, product_id in branch_product_keys:
            branch = Branch.browse(branch_id) if branch_id else Branch
            product = Product.browse(product_id)
            entries = sorted(
                ledger_by_key.get((branch_id, product_id), []),
                key=lambda entry: (
                    entry['sort_date'] or self._opening_datetime(),
                    entry['sort_id'],
                ),
            )
            opening = opening_by_key.get((branch_id, product_id))
            if opening is None:
                opening = self._opening_balance(company, branch, product)
            if product.uom_id:
                opening = product.uom_id.round(opening)
            rows = self._rows_with_running_balance(opening, entries)
            if product.uom_id and rows:
                for row in rows:
                    if row.get('saldo') != '' and row.get('saldo') is not None:
                        row['saldo'] = product.uom_id.round(row['saldo'])
            pages.append({
                **self._branch_report_header(branch, company),
                **self._product_section_header(product),
                'rows': rows,
            })

        return pages

    def action_print_pdf(self):
        self.ensure_one()
        report = self.env.ref(
            'gn_labhospy.action_report_controlled_substances',
            raise_if_not_found=True,
        )
        return report.report_action(self)

    def action_export_html_browser(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/report/html/gn_labhospy.report_controlled_substances_html/%s' % self.id,
            'target': 'new',
        }

    def action_export_xlsx(self):
        self.ensure_one()
        report = self.env.ref(
            'gn_labhospy.action_report_controlled_substances_xlsx',
            raise_if_not_found=True,
        )
        return report.report_action(self)


class ReportGnLabhospyControlledSubstances(models.AbstractModel):
    _name = 'report.gn_labhospy.report_controlled_substances_document'
    _description = 'PDF sustancias controladas'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['gn.labhospy.controlled.substances.report.wizard'].browse(docids)
        wizard.ensure_one()
        company = wizard.company_id

        def fmt_qty(val):
            if val == '' or val is None:
                return ''
            return formatLang(self.env, val, digits=2)

        pages = wizard._build_ledger_sections()

        ts = fields.Datetime.context_timestamp(wizard, fields.Datetime.now())

        return {
            'doc_ids': docids,
            'docs': wizard,
            'company': company,
            'pages': pages,
            'fmt_qty': fmt_qty,
            'report_title': _('Venta de Sustancias Químicas Controladas'),
            'period_from': wizard._format_sc_report_date(wizard.date_from),
            'period_to': wizard._format_sc_report_date(wizard.date_to),
            'print_date': ts.strftime('%d/%m/%Y'),
            'print_time': ts.strftime('%H:%M:%S'),
        }
