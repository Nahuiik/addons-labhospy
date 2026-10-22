import logging

from odoo import fields, models, api, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_is_zero, float_round

_logger = logging.getLogger(__name__)

# Nombre en borrador que no dispara ir.sequence en stock_landed_costs.create (evita consumir
# número si el registro nunca se valida). El número oficial se asigna en button_validate.
_LANDED_COST_DRAFT_NAME_PLACEHOLDER = '/'

# Evitar recursión al sincronizar price_unit (moneda compañía, p. ej. HNL) desde tasa y montos
_CTX_SKIP_LANDED_LINE_PU = 'skip_landed_line_price_recompute'


class StockLandedCost(models.Model):
    _inherit = 'stock.landed.cost'

    margin_last_applied_on = fields.Datetime(
        string='Última aplicación margen venta',
        readonly=True,
        copy=False,
    )
    sale_margin_history_ids = fields.One2many(
        'landed.cost.sale.margin.history',
        'landed_cost_id',
        string='Histórico margen venta',
        readonly=True,
    )

    vendor_bills_ids = fields.Many2many(
        'account.move',
        string="Vendor Bills",
        domain=[
            ('move_type', '=', 'in_invoice'),
            ('state', 'in', ['draft', 'posted']),
            ('invoice_line_ids.product_id.landed_cost_ok', '=', True),
        ],
    )

    amount_total_dollar = fields.Float(string="Total Amount in USD", compute='_compute_amount_total_dollar',
                                       digits=(12, 2), store=True)

    @api.depends('cost_lines.amount_dollar')
    def _compute_amount_total_dollar(self):
        for record in self:
            record.amount_total_dollar = sum(record.cost_lines.mapped('amount_dollar'))

    @api.onchange('vendor_bills_ids')
    def _onchange_vendor_bills_ids(self):
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug("Onchange vendor_bills_ids triggered for cost %s with bills %s", self.id or 'new', self.vendor_bills_ids.ids)
        commands = self._prepare_vendor_bill_line_commands()
        if commands:
            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug("Applying commands on onchange: %s", commands)
            self.cost_lines = commands

    def _get_selected_vendor_bill_ids(self):
        """Return the ids of the vendor bills selected in vendor_bills_ids."""
        selected_ids = set()
        for bill in self.vendor_bills_ids:
            bill_origin = bill._origin if getattr(bill, '_origin', False) else None
            bill_id = bill_origin.id if bill_origin and bill_origin.id else bill.id
            if bill_id:
                selected_ids.add(bill_id)
        return selected_ids

    def _get_lines_to_remove_and_existing_bills(self, selected_bill_ids):
        """Genera las líneas a eliminar y los nombres de las facturas ya existentes en cost_lines."""
        remove_lines = []
        existing_vendor_bills = set()
        existing_vendor_bill_line_ids = set()
        for line in self.cost_lines:
            bill = line.vendor_bill_id_lc
            if not bill:
                continue
            bill_origin = bill._origin if getattr(bill, '_origin', False) else None
            bill_id = bill_origin.id if bill_origin and bill_origin.id else bill.id
            if not bill_id:
                continue
            if bill_id not in selected_bill_ids:
                remove_lines.append((2, line.id, 0))
                continue
            existing_vendor_bills.add(bill_id)
            bill_line = line.vendor_bill_line_id_lc
            if bill_line:
                bill_line_origin = bill_line._origin if getattr(bill_line, '_origin', False) else None
                bill_line_id = bill_line_origin.id if bill_line_origin and bill_line_origin.id else bill_line.id
                if bill_line_id:
                    existing_vendor_bill_line_ids.add((bill_id, bill_line_id))
                else:
                    existing_vendor_bill_line_ids.add(('legacy', bill_id))
            else:
                existing_vendor_bill_line_ids.add(('legacy', bill_id))
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(
                "Computed removals %s and existing %s for selected %s on cost %s",
                [cmd[1] for cmd in remove_lines], list(existing_vendor_bills), selected_bill_ids, self.id or 'new',
                )
        return remove_lines, existing_vendor_bills, existing_vendor_bill_line_ids

    def _create_new_lines(self, existing_vendor_bill_line_ids):
        """Create the cost lines for the vendor bills that are not already present."""
        new_lines = []
        usd_currency = self.env.ref('base.USD', raise_if_not_found=False)

        for bill in self.vendor_bills_ids:
            bill_origin = bill._origin if getattr(bill, '_origin', False) else None
            bill_id = bill_origin.id if bill_origin and bill_origin.id else bill.id
            if not bill_id:
                continue
            if ('legacy', bill_id) in existing_vendor_bill_line_ids:
                if _logger.isEnabledFor(logging.DEBUG):
                    _logger.debug("Skipping bill %s because existing lines are legacy entries without tracking information", bill_id)
                continue

            company = (bill_origin or bill).company_id
            company_currency = company.currency_id
            currency = (bill_origin or bill).currency_id
            conversion_date = (bill_origin or bill).invoice_date or (bill_origin or bill).date or fields.Date.context_today(self)
            rate_usd_to_company = 1.0
            if usd_currency:
                rate_usd_to_company = usd_currency._get_conversion_rate(usd_currency, company_currency, company, conversion_date)

            document_type = ''
            real_bill = bill_origin or bill
            if hasattr(real_bill, 'l10n_latam_document_type_id') and real_bill.l10n_latam_document_type_id:
                document_type = real_bill.l10n_latam_document_type_id.doc_code_prefix or real_bill.l10n_latam_document_type_id.display_name

            def _is_landed_line(line):
                product = line.product_id
                if not product:
                    return False
                if line.display_type and line.display_type not in ('product',):
                    return False
                # Solo agregar productos marcados como costo en destino (landed_cost_ok = True)
                if hasattr(product, 'landed_cost_ok'):
                    return product.landed_cost_ok
                # Si el producto no tiene el atributo landed_cost_ok, no agregarlo
                return False

            invoice_lines = real_bill.invoice_line_ids
            eligible_lines = invoice_lines.filtered(_is_landed_line)
            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug(
                    "Bill %s eligible invoice lines: %s",
                    bill_id,
                    [(line.id, getattr(line.product_id, 'display_name', 'n/a'), bool(getattr(line.product_id, 'landed_cost_ok', False)), line.display_type) for line in invoice_lines],
                )
            for line in eligible_lines:
                line_origin = line._origin if getattr(line, '_origin', False) else None
                line_id = line_origin.id if line_origin and line_origin.id else line.id
                key = (bill_id, line_id) if line_id else None
                if key and key in existing_vendor_bill_line_ids:
                    if _logger.isEnabledFor(logging.DEBUG):
                        _logger.debug("Skipping invoice line %s for bill %s because it already exists on cost %s", line_id, bill_id, self.id or 'new')
                    continue
                account_id = self._get_cost_line_account(line.product_id)
                price_company_currency = currency._convert(line.price_subtotal, company_currency, company, conversion_date)
                # Monto en dólares solo si la factura está en USD
                if usd_currency and currency == usd_currency:
                    amount_usd = line.price_subtotal
                else:
                    amount_usd = 0.0

                line_values = {
                    'product_id': line.product_id.id,
                    'name': line.name,
                    'split_method': line.product_id.product_tmpl_id.split_method_landed_cost or 'equal',
                    'invoice_amount_lc': line.price_subtotal,
                    'price_unit': price_company_currency,
                    'account_id': account_id,
                    'vendor_bill_id_lc': bill_id,
                    'currency_id_lc': currency.id,
                    'currency_rate_lc': rate_usd_to_company,
                    'vendor_id_lc': real_bill.partner_id.id,
                    'date_currency_rate': conversion_date,
                    'amount_dollar': amount_usd,
                    'currency_usd': usd_currency.id if usd_currency else False,
                    'type_document_bill': document_type,
                    'vendor_bill_line_id_lc': line_id,
                }
                new_lines.append((0, 0, line_values))
                if key:
                    if ('legacy', bill_id) in existing_vendor_bill_line_ids:
                        existing_vendor_bill_line_ids.discard(('legacy', bill_id))
                    existing_vendor_bill_line_ids.add(key)
                if _logger.isEnabledFor(logging.DEBUG):
                    _logger.debug("Prepared new cost line values for bill %s on cost %s: %s", bill_id, self.id or 'new', line_values)
        return new_lines

    def _prepare_vendor_bill_line_commands(self):
        """Build the One2many commands needed to sync cost lines with selected vendor bills."""
        selected_bill_ids = self._get_selected_vendor_bill_ids()
        remove_lines, _existing_bill_ids, existing_line_ids = self._get_lines_to_remove_and_existing_bills(selected_bill_ids)
        new_lines = self._create_new_lines(existing_line_ids)
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(
                "Commands prepared for cost %s: remove %s, create %s new entries",
                self.id or 'new', remove_lines, len(new_lines),
            )
        commands = remove_lines + new_lines
        return commands

    def _sync_cost_lines_with_vendor_bills(self):
        """Ensure cost lines mirror the selected vendor bills when the record is saved."""
        for cost in self:
            commands = cost._prepare_vendor_bill_line_commands()
            if commands:
                if _logger.isEnabledFor(logging.DEBUG):
                    _logger.debug("Syncing cost lines for cost %s with commands %s", cost.id, commands)
                cost.with_context(
                    skip_vendor_bill_sync=True,
                    skip_cost_lines_check=True,
                ).write({'cost_lines': commands})

    @api.constrains('cost_lines')
    def _check_cost_lines_required(self):
        if self.env.context.get('skip_cost_lines_check'):
            return
        for cost in self:
            if not cost.cost_lines:
                raise ValidationError(
                    _('Debe agregar al menos una línea en Costos adicionales.')
                )

    def unlink(self):
        raise UserError(
            _('No se pueden eliminar los costos en destino. Use cancelar o los asientos inversos según su política contable.')
        )

    def action_open_sale_margin_wizard(self):
        self.ensure_one()
        if not self.env.user.has_group('invoice_in_landed_cost.group_landed_cost_apply_sale_margin'):
            raise AccessError(_(
                'No tiene permiso para abrir el asistente de margen de venta. '
                'Pídale a un administrador el grupo «Aplicar margen de venta en costeo».'
            ))
        if self.state != 'done':
            raise UserError(_(
                'El asistente de margen de venta solo está disponible cuando el costeo en destino '
                'está validado (registrado). Valide primero el costeo y vuelva a intentarlo.'
            ))
        if not self.valuation_adjustment_lines:
            raise UserError(
                _('Calcule primero el costeo (botón Calcular) para obtener líneas de valoración.')
            )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Margen venta'),
            'res_model': 'landed.cost.sale.margin.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_landed_cost_id': self.id},
        }

    def _is_provisional_landed_cost_name(self, name):
        """True si el costeo aún no tiene referencia definitiva de secuencia."""
        if name is False or name is None:
            return True
        if isinstance(name, str) and not name.strip():
            return True
        if name == _LANDED_COST_DRAFT_NAME_PLACEHOLDER:
            return True
        if name == 'New':
            return True
        if name == _('New'):
            return True
        return False

    def _assign_landed_cost_sequence_if_needed(self):
        """Consume stock.landed.cost solo al validar; borradores usan '/' hasta entonces."""
        for cost in self:
            if cost.state != 'draft':
                continue
            if not cost._is_provisional_landed_cost_name(cost.name):
                continue
            next_name = cost.with_company(cost.company_id).env['ir.sequence'].next_by_code(
                'stock.landed.cost'
            )
            if not next_name:
                raise UserError(_(
                    'No se pudo obtener el siguiente número de la secuencia de costos en destino '
                    '(código stock.landed.cost). Revise la configuración de secuencias.'
                ))
            cost.write({'name': next_name})

    def button_validate(self):
        if not self.env.user.has_group('invoice_in_landed_cost.group_landed_cost_validate'):
            raise AccessError(_(
                'No tiene permiso para validar costos en destino. '
                'Pídale a un administrador el grupo «Validar costos en destino».'
            ))
        self._assign_landed_cost_sequence_if_needed()
        return super().button_validate()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            name = vals.get('name', _('New'))
            if name in (False, None, '') or name == _('New') or name == 'New':
                vals['name'] = _LANDED_COST_DRAFT_NAME_PLACEHOLDER
        records = super(
            StockLandedCost,
            self.with_context(skip_cost_lines_check=True),
        ).create(vals_list)
        records_to_sync = records.filtered(lambda c: c.vendor_bills_ids)
        if records_to_sync and _logger.isEnabledFor(logging.DEBUG):
            _logger.debug("Post-create vendor bill sync for landed costs %s", records_to_sync.ids)
        records_to_sync.with_context(skip_vendor_bill_sync=True)._sync_cost_lines_with_vendor_bills()
        for cost in records:
            if not cost.cost_lines:
                raise ValidationError(
                    _('Debe agregar al menos una línea en Costos adicionales.')
                )
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'vendor_bills_ids' in vals and not self.env.context.get('skip_vendor_bill_sync'):
            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug("Write triggered vendor bill sync for costs %s with vals %s", self.ids, vals)
            self._sync_cost_lines_with_vendor_bills()
        return res

    def _get_cost_line_account(self, product):
        """Cuenta para líneas de costo en destino (alineada con stock.landed.cost.lines en Odoo 19).

        En versiones antiguas existía property_stock_account_input_categ_id en la categoría;
        en 19+ las cuentas de stock vienen de get_product_accounts() (p. ej. stock_valuation,
        stock_variation) y el gasto por categoría en property_account_expense_categ_id.
        """
        tmpl = product.product_tmpl_id
        accounts = tmpl.get_product_accounts()
        # Misma prioridad de idea que en anglo-saxon: gasto / variación; stock_input es clave heredada.
        account = (
            accounts.get('expense')
            or accounts.get('stock_variation')
            or accounts.get('stock_input')
        )
        categ = product.categ_id
        if not account and categ:
            account = categ.property_account_expense_categ_id
        if not account and hasattr(product, 'property_account_expense_id'):
            account = product.property_account_expense_id
        if not account and categ:
            account = categ.property_stock_valuation_account_id
        return account.id if account else False

    def get_purchase_order_name(self, line):
        """Devuelve el nombre de la orden de compra o un mensaje predeterminado si no está disponible."""
        return line.purchase_order.name if line.purchase_order else "PO Not Available"

    def get_order_line_data(self, line):
        """Devuelve la unidad de precio, el subtotal del precio y la unidad de la línea de orden de compra correspondiente"""
        price_unit = price_subtotal = unit = 0
        if line.purchase_order:
            for order_line in line.purchase_order.order_line:
                if order_line.product_id == line.product_id:
                    price_unit = round(order_line.price_subtotal / order_line.product_qty, 2)
                    price_subtotal = order_line.price_subtotal
                    unit = order_line.product_uom.name
                    break
        return price_unit, price_subtotal, unit

    def compute_landed_cost(self):
        """Asignar el purchase order a los ajustes"""
        res = super().compute_landed_cost()
        self._assign_purchase_order_to_adjustment_lines()
        # Actualizar el resumen por producto
        if self.id:
            self.env['landed.cost.product.summary'].create_summary_lines(self)
        return res

    def _assign_purchase_order_to_adjustment_lines(self):
        """Asignar la orden de compra a cada línea de ajuste de valoración según el picking relacionado."""
        for cost in self:
            purchase_map = {picking.id: picking.purchase_id for picking in cost.picking_ids if picking.purchase_id}

            for adjustment_line in cost.valuation_adjustment_lines:
                picking_id = adjustment_line.move_id.picking_id.id
                adjustment_line.purchase_order = purchase_map.get(picking_id)

    def action_report_landed_cost(self):
        """Acción para imprimir el reporte de costo en destino"""
        self.ensure_one()
        return self.env.ref('invoice_in_landed_cost.action_report_landed_cost').report_action(self)

    @api.depends(
        'valuation_adjustment_lines',
        'valuation_adjustment_lines.product_id',
        'valuation_adjustment_lines.quantity',
        'valuation_adjustment_lines.former_cost',
        'valuation_adjustment_lines.additional_landed_cost',
        'valuation_adjustment_lines.final_cost',
        'sale_margin_history_ids',
        'sale_margin_history_ids.line_ids',
    )
    def _compute_product_summary_lines(self):
        """Calcula y actualiza las líneas de resumen por producto"""
        for record in self:
            if record.id and record.valuation_adjustment_lines:
                # Crear o actualizar las líneas de resumen
                summary_model = self.env['landed.cost.product.summary']
                summary_model.create_summary_lines(record)
                record.product_summary_ids = summary_model.search([('landed_cost_id', '=', record.id)])
            else:
                record.product_summary_ids = False

    product_summary_ids = fields.One2many(
        'landed.cost.product.summary',
        'landed_cost_id',
        string='Product Summary',
        compute='_compute_product_summary_lines',
        store=False,
    )

    picking_purchase_order_ids = fields.Many2many(
        'purchase.order',
        'stock_landed_cost_purchase_order_rel',
        'landed_cost_id',
        'purchase_order_id',
        string='Órdenes de compra',
        compute='_compute_picking_related_info',
        store=True,
    )
    picking_vendor_ids = fields.Many2many(
        'res.partner',
        'stock_landed_cost_vendor_rel',
        'landed_cost_id',
        'partner_id',
        string='Proveedores',
        compute='_compute_picking_related_info',
        store=True,
    )
    picking_purchase_order_display = fields.Char(
        string='Órdenes de compra (resumen)',
        compute='_compute_picking_related_info',
        store=True,
    )
    picking_vendor_display = fields.Char(
        string='Proveedores (resumen)',
        compute='_compute_picking_related_info',
        store=True,
    )

    @api.depends('picking_ids', 'picking_ids.purchase_id', 'picking_ids.partner_id')
    def _compute_picking_related_info(self):
        for cost in self:
            pickings = cost.picking_ids
            purchase_orders = pickings.mapped('purchase_id').filtered(lambda po: po)
            vendors = pickings.mapped('partner_id').filtered(lambda p: p)
            cost.picking_purchase_order_ids = [(6, 0, purchase_orders.ids)]
            cost.picking_vendor_ids = [(6, 0, vendors.ids)]
            cost.picking_purchase_order_display = ', '.join(
                dict.fromkeys(purchase_orders.mapped('name'))
            )
            cost.picking_vendor_display = ', '.join(
                dict.fromkeys(vendors.mapped('name'))
            )

    def get_costs_by_product(self):
        """Agrupa los costos por producto y calcula el resumen"""
        self.ensure_one()
        products_summary = {}
        
        # Primero, obtener las cantidades reales de los movimientos de stock de los pickings
        # Esto evita duplicar cantidades cuando hay múltiples líneas de ajuste para el mismo producto
        product_quantities = {}
        for picking in self.picking_ids:
            for move in picking.move_ids:
                if move.state == 'done' and move.product_id:
                    product_id = move.product_id.id
                    # Sumar la cantidad realmente recibida
                    # En Odoo 19, cuando el movimiento está 'done', podemos obtener la cantidad desde move_line_ids
                    if product_id not in product_quantities:
                        product_quantities[product_id] = 0.0
                    # Intentar obtener la cantidad desde move_line_ids primero
                    if move.move_line_ids:
                        # Sumar las cantidades de las líneas de movimiento (qty_done o quantity_done)
                        qty_done = 0.0
                        for move_line in move.move_line_ids:
                            # Intentar qty_done primero, luego quantity_done como fallback
                            qty_done += getattr(move_line, 'qty_done', 0.0) or getattr(move_line, 'quantity_done', 0.0) or 0.0
                        if qty_done > 0:
                            product_quantities[product_id] += qty_done
                        else:
                            # Si no hay qty_done, usar la cantidad del movimiento
                            product_quantities[product_id] += move.quantity
                    else:
                        # Si no hay move_line_ids, usar la cantidad del movimiento cuando está en estado done
                        product_quantities[product_id] += move.quantity
        
        seen_former_keys = set()
        for adj_line in self.valuation_adjustment_lines:
            product = adj_line.product_id
            if not product:
                continue

            product_key = product.id
            if product_key not in products_summary:
                qty = product_quantities.get(product_key, adj_line.quantity)
                products_summary[product_key] = {
                    'product_id': product.id,
                    'product_name': product.display_name,
                    'quantity': qty,
                    'original_value': 0.0,
                    'total_landed_cost': 0.0,
                    'final_value': 0.0,
                }

            if adj_line.move_id:
                fk = (product_key, adj_line.move_id.id)
            else:
                fk = (product_key, 'adj', adj_line.id)
            if fk not in seen_former_keys:
                products_summary[product_key]['original_value'] += adj_line.former_cost
                seen_former_keys.add(fk)

            products_summary[product_key]['total_landed_cost'] += adj_line.additional_landed_cost

        for product_key in products_summary:
            s = products_summary[product_key]
            s['final_value'] = s['original_value'] + s['total_landed_cost']
            qty = s['quantity']
            s['unit_cost'] = s['final_value'] / qty if qty > 0 else 0.0
        
        # Convertir a lista ordenada por nombre de producto
        result = []
        for product_key in sorted(products_summary.keys(), key=lambda k: products_summary[k]['product_name']):
            result.append(products_summary[product_key])
        
        return result

class StockLandedCostLine(models.Model):
    _inherit = 'stock.landed.cost.lines'

    @api.model
    def _usd_currency(self):
        return self.env.ref('base.USD', raise_if_not_found=False)

    def _clear_amount_dollar_unless_usd(self):
        """No mantener monto en USD si la moneda de la línea no es USD."""
        usd = self._usd_currency()
        to_zero = self.env['stock.landed.cost.lines']
        for line in self:
            if not line.amount_dollar:
                continue
            if usd and line.currency_id_lc and line.currency_id_lc == usd:
                continue
            to_zero |= line
        if to_zero:
            to_zero.with_context(skip_usd_amount_sanitize=True).write({'amount_dollar': 0.0})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get('skip_usd_amount_sanitize'):
            records.with_context(skip_usd_amount_sanitize=True)._clear_amount_dollar_unless_usd()
        if not self.env.context.get(_CTX_SKIP_LANDED_LINE_PU):
            records._apply_price_unit_from_currency_fields()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_usd_amount_sanitize'):
            self.with_context(skip_usd_amount_sanitize=True)._clear_amount_dollar_unless_usd()
        if not self.env.context.get(_CTX_SKIP_LANDED_LINE_PU):
            recompute_triggers = {
                'currency_rate_lc', 'amount_dollar', 'date_currency_rate',
                'currency_id_lc', 'invoice_amount_lc',
            }
            if recompute_triggers & vals.keys():
                self._apply_price_unit_from_currency_fields()
        return res

    vendor_id_lc = fields.Many2one('res.partner', string="Vendor", store=True)
    vendor_bill_id_lc = fields.Many2one('account.move', string="Vendor Bill", store=True)
    vendor_bill_line_id_lc = fields.Many2one('account.move.line', string="Vendor Bill Line", store=True)
    currency_id_lc = fields.Many2one('res.currency', string="Currency", store=True)
    invoice_amount_lc = fields.Float(string='Invoice Amount', store=True)
    date_currency_rate = fields.Date(string='Date', store=True)
    # Cuatro decimales: alinear con tasa USD vs moneda compañía (ej. 26.6966). El nombre
    # digits="Exchange Rate" suele no existir en decimal.precision y entonces se usan 2 decimales.
    currency_rate_lc = fields.Float(string='Currency Rate', digits=(16, 4), store=True)
    currency_usd = fields.Many2one('res.currency', string="Currency USD", default=lambda self: self.get_currency_usd(),
                                   store=True)
    amount_dollar = fields.Monetary(string='Amount Dollar', currency_field='currency_usd', store=True)
    type_document_bill = fields.Char(string='Type Document', store=True)

    @api.onchange('currency_id_lc')
    def _onchange_currency_id_lc_usd_amount(self):
        """Si la moneda no es USD, el monto en dólares no aplica."""
        usd_currency = self._usd_currency()
        for line in self:
            if not usd_currency or not line.currency_id_lc or line.currency_id_lc != usd_currency:
                line.amount_dollar = 0.0

    def _price_unit_from_usd_line_rate(self, line, company, company_currency, usd_currency):
        """Coste en moneda de la compañía: monto USD * tasa (misma tasa mostrada en la línea)."""
        if not (
            usd_currency
            and line.currency_id_lc
            and line.currency_id_lc == usd_currency
            and (line.amount_dollar or 0.0)
        ):
            return None
        rate = line.currency_rate_lc
        if not rate:
            return company_currency.round(0.0)
        return company_currency.round((line.amount_dollar or 0.0) * rate)

    def _get_price_unit_in_company_currency(self):
        """Coste (price_unit) en moneda de la compañía (HNL, etc.): alinea onchange, write y create."""
        self.ensure_one()
        usd_currency = self._usd_currency()
        company = self.cost_id.company_id or self.env.company
        company_currency = company.currency_id
        conversion_date = self.date_currency_rate or fields.Date.context_today(self)
        is_usd_line = bool(
            usd_currency and self.currency_id_lc and self.currency_id_lc == usd_currency
        )
        if is_usd_line and (self.amount_dollar or 0.0) and usd_currency:
            pu = self._price_unit_from_usd_line_rate(
                self, company, company_currency, usd_currency
            )
            if pu is not None:
                return float_round(
                    pu,
                    precision_rounding=company_currency.rounding,
                )
        currency = self.currency_id_lc or company_currency
        base_amount = self.invoice_amount_lc or 0.0
        conv = currency._convert(
            base_amount, company_currency, company, conversion_date
        )
        return float_round(
            conv,
            precision_rounding=company_currency.rounding,
        )

    def _apply_price_unit_from_currency_fields(self):
        """Recalcula el coste en moneda de la compañía al persistir tasa o montos (p. ej. lista editable)."""
        for line in self:
            new_pu = line._get_price_unit_in_company_currency()
            if new_pu is None:
                continue
            comp_currency = line.cost_id.currency_id
            rounding = comp_currency.rounding or 0.0001
            if float_is_zero((line.price_unit or 0.0) - new_pu, precision_rounding=rounding):
                continue
            line.with_context(**{_CTX_SKIP_LANDED_LINE_PU: True}).write({'price_unit': new_pu})

    @api.onchange('date_currency_rate', 'amount_dollar', 'currency_id_lc')
    def update_price_unit(self):
        usd_currency = self._usd_currency()
        for line in self:
            company = line.cost_id.company_id or self.env.company
            company_currency = company.currency_id
            conversion_date = line.date_currency_rate or fields.Date.context_today(line)

            if usd_currency:
                line.currency_rate_lc = usd_currency._get_conversion_rate(
                    usd_currency, company_currency, company, conversion_date
                )
            else:
                line.currency_rate_lc = 1.0

            line.price_unit = line._get_price_unit_in_company_currency()

    @api.onchange('currency_rate_lc')
    def _onchange_currency_rate_lc_recalc(self):
        """Al ajustar la tasa manualmente, el coste en moneda de la compañía debe actualizarse."""
        for line in self:
            line.price_unit = line._get_price_unit_in_company_currency()

    @api.onchange('price_unit')
    def update_price_unit_pen(self):
        """Coste (HNL) editado: coherir USD con tasa de la línea. No reescribir tasa con Odoo (rompe tasa manual)."""
        usd_currency = self._usd_currency()
        for line in self:
            company = line.cost_id.company_id or self.env.company
            company_currency = company.currency_id
            conversion_date = line.date_currency_rate or fields.Date.context_today(line)
            is_usd_line = bool(
                usd_currency and line.currency_id_lc and line.currency_id_lc == usd_currency
            )
            if is_usd_line and usd_currency:
                # HNL = USD × tasa: el USD se deduce con la **tasa de la línea** (p. ej. manual), no con _convert
                # (que usaría otra tasa y recalculaba el monto en USD al cambiar solo la tasa).
                rate = line.currency_rate_lc or 0.0
                if not rate or float_is_zero(rate, precision_rounding=0.0001):
                    line.amount_dollar = 0.0
                else:
                    usd_unrounded = (line.price_unit or 0.0) / rate
                    line.amount_dollar = usd_currency.round(usd_unrounded) if usd_currency else usd_unrounded
            else:
                if usd_currency:
                    line.currency_rate_lc = usd_currency._get_conversion_rate(
                        usd_currency, company_currency, company, conversion_date
                    )
                else:
                    line.currency_rate_lc = 1.0
                line.amount_dollar = 0.0

    def get_currency_usd(self):
        """Obtener el currency USD"""
        return self.env.ref('base.USD', raise_if_not_found=False)

class AdjustmentLines(models.Model):
    _inherit = 'stock.valuation.adjustment.lines'

    purchase_order = fields.Many2one('purchase.order', string='Purchase Order', readonly=True)
