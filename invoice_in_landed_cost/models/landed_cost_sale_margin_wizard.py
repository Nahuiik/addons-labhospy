# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools.float_utils import float_round


class LandedCostSaleMarginWizard(models.TransientModel):
    _name = 'landed.cost.sale.margin.wizard'
    _description = 'Asistente margen de venta sobre costeo en destino'

    landed_cost_id = fields.Many2one(
        'stock.landed.cost',
        string='Costo en destino',
        required=True,
        ondelete='cascade',
    )
    global_margin_percent = fields.Float(
        string='% Margen global',
        digits=(16, 4),
        help='Aplicar a todas las líneas con el botón correspondiente.',
    )
    line_ids = fields.One2many(
        'landed.cost.sale.margin.wizard.line',
        'wizard_id',
        string='Productos',
    )
    currency_id = fields.Many2one(
        related='landed_cost_id.company_id.currency_id',
        string='Moneda',
        readonly=True,
    )

    def _check_sale_margin_access(self):
        if not self.env.user.has_group('invoice_in_landed_cost.group_landed_cost_apply_sale_margin'):
            raise AccessError(_(
                'No tiene permiso para usar el asistente de margen de venta en costeos en destino.'
            ))

    @api.model
    def default_get(self, fields_list):
        self._check_sale_margin_access()
        res = super().default_get(fields_list)
        lc_id = self.env.context.get('default_landed_cost_id')
        if not lc_id and self.env.context.get('active_model') == 'stock.landed.cost':
            lc_id = self.env.context.get('active_id')
        if not lc_id:
            return res
        lc = self.env['stock.landed.cost'].browse(lc_id)
        if not lc.exists():
            return res
        if not lc.valuation_adjustment_lines:
            raise UserError(_(
                'No hay líneas de ajuste de valoración. Calcule primero el costeo en destino.'
            ))
        lines_vals = self._prepare_lines_from_landed_cost(lc)
        if not lines_vals:
            raise UserError(_(
                'No hay productos válidos en el costeo para el asistente. '
                'Calcule el costeo y verifique los ajustes de valoración.'
            ))
        res['landed_cost_id'] = lc.id
        res['line_ids'] = [(0, 0, v) for v in lines_vals]
        return res

    def _prepare_lines_from_landed_cost(self, landed_cost):
        """Usa get_costs_by_product() del costeo (misma lógica que el resumen)."""
        rows = landed_cost.get_costs_by_product()
        vals_list = []
        for row in rows:
            pid = row.get('product_id')
            if not pid:
                continue
            product = self.env['product.product'].browse(pid)
            if not product.exists():
                continue
            qty = row.get('quantity') or 0.0
            unit_cost = row.get('unit_cost', 0.0)
            vals_list.append({
                'product_id': product.id,
                'quantity': qty,
                'unit_cost': unit_cost,
                'price_before_apply': product.lst_price,
                'margin_percent': 0.0,
            })
        return vals_list

    def _ensure_product_lines(self):
        """Si el guardado del formulario llegó sin líneas One2many, recrearlas desde el costeo."""
        Line = self.env['landed.cost.sale.margin.wizard.line']
        for wiz in self:
            if Line.search_count([('wizard_id', '=', wiz.id)]):
                continue
            lc = wiz.landed_cost_id
            if not lc.exists():
                raise UserError(_('No hay costeo en destino asociado al asistente.'))
            vals_list = wiz._prepare_lines_from_landed_cost(lc)
            if not vals_list:
                raise UserError(_(
                    'No hay productos en el costeo para el asistente. '
                    'Verifique el costeo y los ajustes de valoración.'
                ))
            wiz.write({'line_ids': [(0, 0, v) for v in vals_list]})

    def write(self, vals):
        res = super().write(vals)
        Line = self.env['landed.cost.sale.margin.wizard.line']
        for wiz in self:
            if wiz.landed_cost_id and not Line.search_count([('wizard_id', '=', wiz.id)]):
                wiz._ensure_product_lines()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        self._check_sale_margin_access()
        records = super().create(vals_list)
        records._ensure_product_lines()
        return records

    def _get_wizard_lines(self):
        """Líneas del asistente leyendo desde BD (self.line_ids puede quedar vacío en caché tras crear hijos)."""
        self.ensure_one()
        return self.env['landed.cost.sale.margin.wizard.line'].search(
            [('wizard_id', '=', self.id)]
        )

    def _discard_lines_without_product(self):
        """Quita líneas vacías (p. ej. fila nueva de lista editable sin producto)."""
        bad = self._get_wizard_lines().filtered(lambda l: not l.product_id)
        if bad:
            bad.unlink()

    def action_apply_global_margin(self):
        self.ensure_one()
        self._check_sale_margin_access()
        self._ensure_product_lines()
        pct = float(self.global_margin_percent if self.global_margin_percent is not None else 0.0)
        lines = self._get_wizard_lines()
        if not lines:
            raise UserError(_('No hay líneas en el asistente para aplicar el margen.'))
        lines.write({'margin_percent': pct})
        # Recargar el modal sin default_* en contexto: el cliente no refresca el x2many tras el RPC
        # y self.line_ids seguía mostrando margen 0 / PVP sin calcular.
        return {
            'name': _('Margen venta'),
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {},
        }

    def action_apply(self):
        self.ensure_one()
        self._check_sale_margin_access()
        self._discard_lines_without_product()
        self._ensure_product_lines()
        lines = self._get_wizard_lines()
        if not lines:
            raise UserError(_('No hay líneas de producto.'))
        lc = self.landed_cost_id
        prec = self.env['decimal.precision'].precision_get('Product Price')
        body_lines = []
        history_line_vals = []
        for line in lines:
            if line.margin_percent < 0:
                raise UserError(_('El margen no puede ser negativo para el producto %s.') % line.product_id.display_name)
            target_lst = line.price_after_apply
            old_lst = line.price_before_apply
            product = line.product_id.with_context(disable_auto_revaluation=True)
            # lst_price = list_price + price_extra => list_price = target_lst - price_extra
            new_list = target_lst - product.price_extra
            new_list = float_round(new_list, precision_digits=prec)
            product.write({'list_price': new_list})
            new_lst_read = product.lst_price
            if line.unit_cost and line.unit_cost > 0:
                margin_stored = (new_lst_read - line.unit_cost) / line.unit_cost * 100.0
            else:
                margin_stored = line.margin_percent
            tmpl = product.product_tmpl_id
            tmpl.message_post(
                body=_(
                    'Precio de venta actualizado por costeo en destino %(lc)s: %(old)s → %(new)s '
                    '(margen %(mp)s, costo unit. %(uc)s).',
                    lc=lc.display_name,
                    old=old_lst,
                    new=new_lst_read,
                    mp='%.2f %%' % line.margin_percent,
                    uc='%.2f' % line.unit_cost,
                ),
                subtype_xmlid='mail.mt_note',
            )
            body_lines.append(
                '- %s: margen %.2f %%, PVP %s → %s'
                % (product.display_name, line.margin_percent, old_lst, new_lst_read)
            )
            history_line_vals.append({
                'product_id': line.product_id.id,
                'quantity': line.quantity,
                'unit_cost': line.unit_cost,
                'price_before_apply': old_lst,
                'margin_percent': margin_stored,
                'price_target': target_lst,
                'price_applied': new_lst_read,
            })
        lc.message_post(
            body=_('Margen de venta aplicado:\n%s') % '\n'.join(body_lines),
            subtype_xmlid='mail.mt_note',
        )
        lc.margin_last_applied_on = fields.Datetime.now()
        history = self.env['landed.cost.sale.margin.history'].create({
            'landed_cost_id': lc.id,
            'global_margin_percent': float(self.global_margin_percent or 0.0),
        })
        for seq, hvals in enumerate(history_line_vals, start=1):
            hvals['history_id'] = history.id
            hvals['sequence'] = seq * 10
        self.env['landed.cost.sale.margin.history.line'].create(history_line_vals)
        return self.action_print_margin_report()

    def action_print_margin_report(self):
        self.ensure_one()
        self._check_sale_margin_access()
        action = self.env.ref(
            'invoice_in_landed_cost.action_report_landed_cost_margin'
        ).report_action(self)
        action['close_on_report_download'] = True
        return action


class LandedCostSaleMarginWizardLine(models.TransientModel):
    _name = 'landed.cost.sale.margin.wizard.line'
    _description = 'Línea margen venta costeo'

    @api.model_create_multi
    def create(self, vals_list):
        # La lista editable puede intentar crear una fila vacía sin producto al guardar.
        vals_list = [v for v in vals_list if v.get('product_id')]
        if not vals_list:
            return self.browse()
        return super().create(vals_list)

    wizard_id = fields.Many2one(
        'landed.cost.sale.margin.wizard',
        required=True,
        ondelete='cascade',
    )
    currency_id = fields.Many2one(
        related='wizard_id.currency_id',
        string='Moneda',
        readonly=True,
    )
    product_id = fields.Many2one('product.product', string='Producto', required=True, readonly=True)
    quantity = fields.Float(string='Cantidad', digits=(16, 4), readonly=True)
    unit_cost = fields.Float(string='Costo unitario final', digits='Product Price', readonly=True)
    price_before_apply = fields.Float(string='PVP anterior', digits='Product Price', readonly=True)
    margin_percent = fields.Float(string='% Margen', digits=(16, 4))
    price_after_apply = fields.Float(
        string='PVP objetivo',
        compute='_compute_price_after',
        digits='Product Price',
    )

    @api.depends('unit_cost', 'margin_percent')
    def _compute_price_after(self):
        for line in self:
            line.price_after_apply = line.unit_cost * (1.0 + (line.margin_percent or 0.0) / 100.0)
