# -*- coding: utf-8 -*-
from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero


class GnInventoryAdjustment(models.TransientModel):
    _name = 'gn.inventory.adjustment'
    _description = 'Wizard Inventario LabHosPy'

    warehouse_id = fields.Many2one('stock.warehouse', string='Almacén')
    location_id = fields.Many2one('stock.location', string='Ubicación')
    supplier_id = fields.Many2one('gn.labhospy.supplier', string='Proveedor (LabHosPy)')
    model_filter = fields.Char(string='Modelo')
    code_filter = fields.Char(string='Código de Catálogo')
    show_qty = fields.Boolean(string='Mostrar cantidades a la mano', default=True)

    # ── Opciones de filtros para la pantalla OWL ──

    @api.model
    def get_filter_options(self):
        company = self.env.company
        warehouses = self.env['stock.warehouse'].search_read(
            [('company_id', '=', company.id)], ['name', 'view_location_id'], order='name')
        locations = self.env['stock.location'].search_read(
            [('usage', '=', 'internal'), ('company_id', '=', company.id)],
            ['complete_name', 'warehouse_id'], order='complete_name')
        suppliers = self.env['gn.labhospy.supplier'].search_read(
            [], ['name'], order='name')
        return {
            'warehouses': [{'id': w['id'], 'name': w['name']} for w in warehouses],
            'locations': [{
                'id': l['id'],
                'name': l['complete_name'],
                'warehouse_id': l['warehouse_id'] and l['warehouse_id'][0] or False,
            } for l in locations],
            'suppliers': [{'id': s['id'], 'name': s['name']} for s in suppliers],
        }

    # ── Dominio y líneas ──

    @api.model
    def _build_domain(self, filters):
        domain = [
            ('location_id.usage', '=', 'internal'),
            ('company_id', '=', self.env.company.id),
        ]
        location_id = filters.get('location_id')
        warehouse_id = filters.get('warehouse_id')
        if location_id:
            domain.append(('location_id', 'child_of', int(location_id)))
        elif warehouse_id:
            warehouse = self.env['stock.warehouse'].browse(int(warehouse_id))
            domain.append(('location_id', 'child_of', warehouse.view_location_id.id))
        if filters.get('supplier_id'):
            domain.append((
                'product_id.product_tmpl_id.gn_labhospy_supplier_id',
                '=', int(filters['supplier_id'])))
        if filters.get('model_filter'):
            domain.append((
                'product_id.product_tmpl_id.gn_labhospy_model',
                'ilike', filters['model_filter']))
        if filters.get('code_filter'):
            domain.append((
                'product_id.product_tmpl_id.gn_labhospy_catalog_code',
                'ilike', filters['code_filter']))
        return domain

    @api.model
    def _get_lines_data(self, filters):
        quants = self.env['stock.quant'].search(self._build_domain(filters))
        lines = []
        for quant in quants:
            tmpl = quant.product_id.product_tmpl_id
            lines.append({
                'line_key': 'q-%s' % quant.id,
                'quant_id': quant.id,
                'product_id': quant.product_id.id,
                'location_id': quant.location_id.id,
                'lot_name': quant.lot_id.name or '',
                'manual': False,
                'location': quant.location_id.complete_name or '',
                'default_code': quant.product_id.default_code or '',
                'product': quant.product_id.name or '',
                'supplier': tmpl.gn_labhospy_supplier_id.name or '',
                'catalog_code': tmpl.gn_labhospy_catalog_code or '',
                'model': tmpl.gn_labhospy_model or '',
                'lot': quant.lot_id.name or '',
                'uom': quant.product_uom_id.name or '',
                'qty_on_hand': quant.quantity,
                'tracking': quant.product_id.tracking,
            })
        lines.sort(key=lambda l: (l['location'], l['product'], l['lot']))
        return lines

    @api.model
    def get_lines(self, filters):
        return self._get_lines_data(filters)

    @api.model
    def search_products(self, term, limit=20):
        """Productos almacenables para agregarlos aunque no tengan existencia."""
        domain = [
            ('is_storable', '=', True),
            '|', ('company_id', '=', False), ('company_id', '=', self.env.company.id),
        ]
        term = (term or '').strip()
        if term:
            domain += [
                '|', '|', '|',
                ('name', 'ilike', term),
                ('default_code', 'ilike', term),
                ('barcode', 'ilike', term),
                ('product_tmpl_id.gn_labhospy_catalog_code', 'ilike', term),
            ]
        products = self.env['product.product'].search(domain, limit=limit or 20, order='default_code, name')
        return [{
            'id': product.id,
            'name': product.display_name,
            'default_code': product.default_code or '',
            'tracking': product.tracking,
            'uom': product.uom_id.name or '',
        } for product in products]

    @api.model
    def prepare_manual_line(self, product_id, location_id, lot_name=None):
        """Línea de conteo para un producto sin existencia (o ya existente en esa ubicación)."""
        product = self.env['product.product'].browse(int(product_id)).exists()
        location = self.env['stock.location'].browse(int(location_id)).exists()
        if not product or not product.is_storable:
            raise UserError(_('Seleccione un producto almacenable.'))
        if not location or location.usage != 'internal':
            raise UserError(_('Seleccione una ubicación interna.'))
        lot_name = (lot_name or '').strip()
        if product.tracking in ('lot', 'serial') and not lot_name:
            raise UserError(_('Este producto se controla por lote o serie. Indique el número.'))
        if product.tracking == 'none':
            lot_name = ''
        lot = self._find_lot(product, location, lot_name) if lot_name else self.env['stock.lot']
        quant = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id', '=', location.id),
            ('lot_id', '=', lot.id or False),
            ('package_id', '=', False),
            ('owner_id', '=', False),
        ], limit=1)
        tmpl = product.product_tmpl_id
        rounding = product.uom_id.rounding or 0.01
        has_stock = bool(quant) and not float_is_zero(quant.quantity, precision_rounding=rounding)
        return {
            'line_key': ('q-%s' % quant.id) if quant else 'm-%s-%s-%s' % (product.id, location.id, lot_name or '0'),
            'quant_id': quant.id or False,
            'product_id': product.id,
            'location_id': location.id,
            'lot_name': lot.name if lot else lot_name,
            'manual': not has_stock,
            'location': location.complete_name or '',
            'default_code': product.default_code or '',
            'product': product.name or '',
            'supplier': tmpl.gn_labhospy_supplier_id.name or '',
            'catalog_code': tmpl.gn_labhospy_catalog_code or '',
            'model': tmpl.gn_labhospy_model or '',
            'lot': (lot.name if lot else lot_name) or '',
            'uom': product.uom_id.name or '',
            'qty_on_hand': quant.quantity if quant else 0.0,
            'tracking': product.tracking,
        }

    def _find_lot(self, product, location, lot_name):
        company = location.company_id or self.env.company
        return self.env['stock.lot'].search([
            ('product_id', '=', product.id),
            ('name', '=', lot_name),
            '|', ('company_id', '=', False), ('company_id', '=', company.id),
        ], limit=1)

    def _ensure_lot(self, product, location, lot_name):
        lot_name = (lot_name or '').strip()
        if product.tracking == 'none' or not lot_name:
            return self.env['stock.lot']
        lot = self._find_lot(product, location, lot_name)
        if lot:
            return lot
        company = location.company_id or self.env.company
        return self.env['stock.lot'].create({
            'name': lot_name,
            'product_id': product.id,
            'company_id': company.id,
        })

    def _quant_for_adjustment_line(self, item):
        Quant = self.env['stock.quant']
        quant_id = item.get('quant_id')
        if quant_id:
            quant = Quant.browse(int(quant_id)).exists()
            if quant:
                return quant
        product = self.env['product.product'].browse(int(item.get('product_id') or 0)).exists()
        location = self.env['stock.location'].browse(int(item.get('location_id') or 0)).exists()
        if not product or not location:
            return Quant
        lot = self._ensure_lot(product, location, item.get('lot_name'))
        quant = Quant.search([
            ('product_id', '=', product.id),
            ('location_id', '=', location.id),
            ('lot_id', '=', lot.id or False),
            ('package_id', '=', False),
            ('owner_id', '=', False),
        ], limit=1)
        if quant:
            return quant
        return Quant.with_context(inventory_mode=True).create({
            'product_id': product.id,
            'location_id': location.id,
            'lot_id': lot.id or False,
            'inventory_quantity': float(item['counted_qty']),
        })

    def _evidence_body(self, prepared):
        rows = []
        for quant, on_hand, counted in prepared:
            diff = counted - on_hand
            rows.append(
                '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td>'
                '<td style="text-align:right">%s</td>'
                '<td style="text-align:right">%s</td>'
                '<td style="text-align:right">%s</td></tr>' % (
                    escape(quant.location_id.complete_name or ''),
                    escape(quant.product_id.default_code or ''),
                    escape(quant.product_id.display_name or ''),
                    escape(quant.lot_id.name or ''),
                    on_hand,
                    counted,
                    diff,
                )
            )
        intro = _('Procesado desde Wizard Inventario por %s.') % self.env.user.name
        return Markup(
            '<p>%s</p><table class="table table-sm"><thead><tr>'
            '<th>%s</th><th>%s</th><th>%s</th><th>%s</th>'
            '<th>%s</th><th>%s</th><th>%s</th>'
            '</tr></thead><tbody>%s</tbody></table>'
        ) % (
            escape(intro),
            escape(_('Ubicación')),
            escape(_('Código')),
            escape(_('Producto')),
            escape(_('Lote/Serie')),
            escape(_('A la mano')),
            escape(_('Contado')),
            escape(_('Diferencia')),
            Markup(''.join(rows)),
        )

    # ── Aplicar ajuste de inventario ──

    @api.model
    def apply_adjustment(self, lines):
        if not lines:
            raise UserError(_('No hay líneas con cantidad contada para aplicar.'))
        prepared = []
        for item in lines:
            quant = self._quant_for_adjustment_line(item)
            if not quant:
                continue
            counted = float(item['counted_qty'])
            rounding = quant.product_id.uom_id.rounding or 0.01
            if counted < 0:
                raise UserError(_('La cantidad contada no puede ser negativa.'))
            if quant.product_id.tracking == 'serial' and not (
                float_is_zero(counted, precision_rounding=rounding)
                or float_compare(counted, 1.0, precision_rounding=rounding) == 0
            ):
                raise UserError(_(
                    'El producto %s es un número de serie. La cantidad contada debe ser 0 o 1.',
                    quant.product_id.display_name,
                ))
            on_hand = quant.quantity
            quant.with_context(inventory_mode=True).inventory_quantity = counted
            prepared.append((quant, on_hand, counted))
        if not prepared:
            raise UserError(_('Las líneas seleccionadas ya no existen en el inventario.'))
        inventory = self.env['stock.inventory'].create({
            'name': '/',
            'state': 'confirm',
            'company_id': self.env.company.id,
        })
        quants = self.env['stock.quant'].browse([quant.id for quant, _on_hand, _counted in prepared])
        quants.sudo().write({'inventory_id': inventory.id})
        result = quants.with_context(
            inventory_mode=True,
            inventory_name='/',
        ).action_apply_inventory()
        inventory.message_post(body=self._evidence_body(prepared), subtype_xmlid='mail.mt_note')
        open_action = {
            'type': 'ir.actions.act_window',
            'name': inventory.display_name,
            'res_model': 'stock.inventory',
            'res_id': inventory.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }
        return {
            'applied': len(prepared),
            'inventory_id': inventory.id,
            'inventory_name': inventory.display_name,
            'action': result if isinstance(result, dict) else open_action,
            'conflict': isinstance(result, dict),
        }

    # ── Impresión PDF / Excel ──

    @api.model
    def print_report(self, filters, fmt):
        vals = {
            'warehouse_id': int(filters['warehouse_id']) if filters.get('warehouse_id') else False,
            'location_id': int(filters['location_id']) if filters.get('location_id') else False,
            'supplier_id': int(filters['supplier_id']) if filters.get('supplier_id') else False,
            'model_filter': filters.get('model_filter') or False,
            'code_filter': filters.get('code_filter') or False,
            'show_qty': bool(filters.get('show_qty')),
        }
        wizard = self.create(vals)
        if fmt == 'xlsx':
            report = self.env.ref('gn_inventory_ajustment.action_report_inventory_adjustment_xlsx')
        else:
            report = self.env.ref('gn_inventory_ajustment.action_report_inventory_adjustment_pdf')
        return report.report_action(wizard, config=False)

    def _wizard_filters(self):
        self.ensure_one()
        return {
            'warehouse_id': self.warehouse_id.id,
            'location_id': self.location_id.id,
            'supplier_id': self.supplier_id.id,
            'model_filter': self.model_filter,
            'code_filter': self.code_filter,
        }

    def get_report_lines(self):
        self.ensure_one()
        return self._get_lines_data(self._wizard_filters())

    def get_report_filters_label(self):
        self.ensure_one()
        parts = []
        if self.warehouse_id:
            parts.append(_('Almacén: %s') % self.warehouse_id.name)
        if self.location_id:
            parts.append(_('Ubicación: %s') % self.location_id.complete_name)
        if self.supplier_id:
            parts.append(_('Proveedor: %s') % self.supplier_id.name)
        if self.model_filter:
            parts.append(_('Modelo: %s') % self.model_filter)
        if self.code_filter:
            parts.append(_('Código: %s') % self.code_filter)
        return ' | '.join(parts) if parts else _('Sin filtros')
