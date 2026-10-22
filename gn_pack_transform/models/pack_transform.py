# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_is_zero


class GnPackTransform(models.Model):
    _name = 'gn.pack.transform'
    _description = 'Transformación paquete → unidad'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, name desc'

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        default=lambda self: _('Nuevo'),
        tracking=True,
    )
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('done', 'Realizado'),
            ('cancel', 'Cancelado'),
        ],
        string='Estado',
        default='draft',
        tracking=True,
    )
    date = fields.Datetime(
        string='Fecha',
        default=fields.Datetime.now,
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Almacén',
        required=True,
        default=lambda self: self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)], limit=1
        ),
    )
    source_product_id = fields.Many2one(
        'product.product',
        string='Producto origen (paquete)',
        required=True,
        domain="[('is_storable', '=', True)]",
        tracking=True,
    )
    source_template_id = fields.Many2one(
        related='source_product_id.product_tmpl_id',
        string='Plantilla origen',
    )
    source_uom_id = fields.Many2one(
        'uom.uom',
        string='UdM origen',
        required=True,
    )
    source_lot_id = fields.Many2one(
        'stock.lot',
        string='Lote origen',
        domain="[('product_id', '=', source_product_id)]",
    )
    source_tracking = fields.Selection(
        related='source_product_id.tracking',
        string='Trazabilidad origen',
    )
    dest_tracking = fields.Selection(
        related='dest_product_id.tracking',
        string='Trazabilidad destino',
    )
    source_qty = fields.Float(
        string='Cantidad origen',
        digits='Product Unit',
        required=True,
        default=1.0,
    )
    dest_product_id = fields.Many2one(
        'product.product',
        string='Producto destino (unidad)',
        required=True,
        domain="[('is_storable', '=', True)]",
        tracking=True,
    )
    dest_uom_id = fields.Many2one(
        'uom.uom',
        string='UdM destino',
        required=True,
    )
    dest_qty = fields.Float(
        string='Cantidad destino',
        digits='Product Unit',
        compute='_compute_dest_qty',
        store=True,
        readonly=False,
    )
    unpack_ratio = fields.Float(
        string='Relación origen → destino',
        digits='Product Unit',
        help='Unidades destino generadas por cada unidad origen (ej. 15 unidades por 1 pack).',
    )
    source_unit_cost = fields.Monetary(
        string='Costo unitario origen',
        currency_field='currency_id',
        compute='_compute_values_preview',
    )
    source_total_value = fields.Monetary(
        string='Valor total origen',
        currency_field='currency_id',
        compute='_compute_values_preview',
    )
    dest_total_value = fields.Monetary(
        string='Valor total destino',
        currency_field='currency_id',
        compute='_compute_values_preview',
        help='Igual al valor total origen: el costo se transfiere íntegro al producto destino.',
    )
    dest_unit_cost = fields.Monetary(
        string='Costo unitario destino',
        currency_field='currency_id',
        compute='_compute_values_preview',
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string='Operación de inventario',
        copy=False,
        readonly=True,
    )
    note = fields.Text(string='Notas')

    @api.depends('source_qty', 'unpack_ratio')
    def _compute_dest_qty(self):
        for record in self:
            ratio = record.unpack_ratio or 0.0
            record.dest_qty = (record.source_qty or 0.0) * ratio if ratio else 0.0

    @api.depends(
        'source_product_id',
        'source_uom_id',
        'source_qty',
        'source_lot_id',
        'dest_product_id',
        'dest_uom_id',
        'dest_qty',
        'company_id',
    )
    def _compute_values_preview(self):
        for record in self:
            if (
                not record.source_product_id
                or not record.dest_product_id
                or not record.source_qty
                or not record.dest_qty
            ):
                record.source_unit_cost = 0.0
                record.source_total_value = 0.0
                record.dest_total_value = 0.0
                record.dest_unit_cost = 0.0
                continue
            total_value = record._get_source_total_value()
            record.source_total_value = total_value
            record.dest_total_value = total_value
            record.source_unit_cost = total_value / record.source_qty if record.source_qty else 0.0
            record.dest_unit_cost = total_value / record.dest_qty if record.dest_qty else 0.0

    @api.onchange('source_product_id')
    def _onchange_source_product_id(self):
        if not self.source_product_id:
            self.source_lot_id = False
            return
        if self.source_product_id.tracking == 'none':
            self.source_lot_id = False
        defaults = self.source_product_id.product_tmpl_id._gn_pack_get_unpack_defaults(
            self.source_product_id,
        )
        self.source_uom_id = defaults.get('source_uom_id')
        self.dest_product_id = defaults.get('dest_product_id')
        self.dest_uom_id = defaults.get('dest_uom_id')
        self.unpack_ratio = defaults.get('unpack_ratio', 0.0)

    @api.onchange('source_qty', 'unpack_ratio')
    def _onchange_unpack_ratio(self):
        if self.unpack_ratio and self.source_qty:
            self.dest_qty = self.source_qty * self.unpack_ratio

    @api.constrains('source_qty', 'dest_qty', 'unpack_ratio')
    def _check_quantities(self):
        for record in self:
            if record.state != 'draft':
                continue
            if record.source_qty <= 0:
                raise UserError(_('La cantidad de origen debe ser mayor que cero.'))
            if record.dest_qty <= 0:
                raise UserError(_('La cantidad destino debe ser mayor que cero.'))
            if record.unpack_ratio <= 0:
                raise UserError(_('Indique la relación paquete → unidades (ej. 15).'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('gn.pack.transform')
                    or _('Nuevo')
                )
        return super().create(vals_list)

    def action_confirm(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_('Solo puede procesar transformaciones en borrador.'))
            record._validate_before_process()
            picking = record._create_and_validate_picking()
            record.write({'state': 'done', 'picking_id': picking.id})
            record.message_post(
                body=_(
                    'Transformación realizada: %(src_qty)s %(src_uom)s de %(src)s → '
                    '%(dest_qty)s %(dest_uom)s de %(dest)s. Valor transferido: %(value)s.',
                    src_qty=record.source_qty,
                    src_uom=record.source_uom_id.display_name,
                    src=record.source_product_id.display_name,
                    dest_qty=record.dest_qty,
                    dest_uom=record.dest_uom_id.display_name,
                    dest=record.dest_product_id.display_name,
                    value=record.source_total_value,
                )
            )
        return True

    def action_cancel(self):
        self.filtered(lambda r: r.state == 'draft').write({'state': 'cancel'})

    def action_set_draft(self):
        self.filtered(lambda r: r.state == 'cancel').write({'state': 'draft'})

    def action_open_picking(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.picking_id.display_name,
            'res_model': 'stock.picking',
            'res_id': self.picking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _validate_before_process(self):
        self.ensure_one()
        if self.source_product_id.tracking != 'none' and not self.source_lot_id:
            raise UserError(_('Indique el lote del producto origen.'))
        if self.dest_product_id.tracking != 'none' and not self.source_lot_id:
            raise UserError(
                _('El producto destino está rastreado por lote; indique el lote origen '
                  'para transferir trazabilidad.')
            )
        self._check_source_availability()

    def _check_source_availability(self):
        self.ensure_one()
        location = self.warehouse_id.lot_stock_id
        qty_available = self.env['stock.quant']._get_available_quantity(
            self.source_product_id,
            location,
            lot_id=self.source_lot_id,
            strict=True,
        )
        rounding = self.source_uom_id.rounding
        if float_compare(qty_available, self.source_qty, precision_rounding=rounding) < 0:
            raise UserError(
                _('Stock insuficiente de %(product)s. Disponible: %(qty)s %(uom)s.',
                  product=self.source_product_id.display_name,
                  qty=qty_available,
                  uom=self.source_uom_id.display_name)
            )

    def _get_source_total_value(self):
        self.ensure_one()
        company = self.company_id
        product = self.source_product_id.with_company(company)
        qty_product_uom = self.source_uom_id._compute_quantity(
            self.source_qty,
            product.uom_id,
        )
        if self.source_lot_id and product.lot_valuated:
            lot = self.source_lot_id.with_company(company)
            unit_cost = lot.standard_price or lot.avg_cost or product.standard_price
        else:
            unit_cost = product.standard_price
        return unit_cost * qty_product_uom

    def _create_and_validate_picking(self):
        self.ensure_one()
        warehouse = self.warehouse_id
        stock_loc = warehouse.lot_stock_id
        production_loc = self.company_id._gn_pack_get_production_location()
        if not production_loc:
            raise UserError(
                _('No se encontró la ubicación de producción para la compañía %(company)s.',
                  company=self.company_id.display_name)
            )

        picking_type = warehouse.int_type_id
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': stock_loc.id,
            'location_dest_id': stock_loc.id,
            'origin': self.name,
            'company_id': self.company_id.id,
            'scheduled_date': self.date,
        })

        move_out = self.env['stock.move'].create({
            'product_id': self.source_product_id.id,
            'product_uom_qty': self.source_qty,
            'product_uom': self.source_uom_id.id,
            'location_id': stock_loc.id,
            'location_dest_id': production_loc.id,
            'picking_id': picking.id,
            'company_id': self.company_id.id,
            'date': self.date,
        })
        move_in = self.env['stock.move'].create({
            'product_id': self.dest_product_id.id,
            'product_uom_qty': self.dest_qty,
            'product_uom': self.dest_uom_id.id,
            'location_id': production_loc.id,
            'location_dest_id': stock_loc.id,
            'picking_id': picking.id,
            'company_id': self.company_id.id,
            'date': self.date,
        })

        self._prepare_move_line(move_out, self.source_lot_id)
        dest_lot = self._get_or_create_dest_lot()
        self._prepare_move_line(move_in, dest_lot)

        picking.action_confirm()
        move_out.write({
            'quantity': move_out.product_uom_qty,
            'picked': True,
        })
        move_out._action_done()
        transferred_value = move_out.value
        if float_is_zero(transferred_value, precision_rounding=self.currency_id.rounding):
            transferred_value = self._get_source_total_value()

        self.env['product.value'].create({
            'move_id': move_in.id,
            'value': transferred_value,
            'description': _('Transformación paquete %(ref)s', ref=self.name),
        })
        move_in.write({
            'quantity': move_in.product_uom_qty,
            'picked': True,
        })
        move_in._action_done()

        if picking.state != 'done':
            picking._action_done()
        return picking

    def _prepare_move_line(self, move, lot):
        line_vals = {
            'move_id': move.id,
            'product_id': move.product_id.id,
            'product_uom_id': move.product_uom.id,
            'quantity': move.product_uom_qty,
            'location_id': move.location_id.id,
            'location_dest_id': move.location_dest_id.id,
            'picked': True,
        }
        if lot and move.product_id.tracking != 'none':
            line_vals['lot_id'] = lot.id
        self.env['stock.move.line'].create(line_vals)

    def _get_or_create_dest_lot(self):
        self.ensure_one()
        if self.dest_product_id.tracking == 'none':
            return self.env['stock.lot']
        if not self.source_lot_id:
            raise UserError(_('Indique el lote origen para crear el lote destino.'))
        Lot = self.env['stock.lot']
        lot = Lot.search([
            ('product_id', '=', self.dest_product_id.id),
            ('name', '=', self.source_lot_id.name),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if lot:
            return lot
        lot_vals = {
            'name': self.source_lot_id.name,
            'product_id': self.dest_product_id.id,
            'company_id': self.company_id.id,
        }
        if 'expiration_date' in self.source_lot_id._fields:
            lot_vals['expiration_date'] = self.source_lot_id.expiration_date
        return Lot.create(lot_vals)
