"""Gastos adicionales por picking + marca de partición para importaciones."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    gn_import_reception_split = fields.Boolean(
        string='Recepción dividida',
        copy=False,
        help='Indica que este picking forma parte de una recepción dividida '
        'planificada de una compra internacional.',
    )
    gn_import_reception_part = fields.Selection(
        [('first', 'Recepción 1'), ('second', 'Recepción 2')],
        string='Parte de la recepción',
        copy=False,
    )
    gn_import_extra_cost_line_ids = fields.One2many(
        'gn.import.extra.cost.line',
        'picking_id',
        string='Gastos adicionales importación',
        copy=False,
    )
    gn_import_landed_cost_ids = fields.Many2many(
        'stock.landed.cost',
        compute='_compute_gn_import_landed_cost_ids',
        string='Costos en destino',
    )
    gn_import_landed_cost_count = fields.Integer(
        compute='_compute_gn_import_landed_cost_ids',
    )

    @api.depends('gn_import_extra_cost_line_ids.landed_cost_line_id')
    def _compute_gn_import_landed_cost_ids(self):
        for picking in self:
            costs = picking.gn_import_extra_cost_line_ids.mapped(
                'landed_cost_line_id.cost_id'
            )
            picking.gn_import_landed_cost_ids = costs
            picking.gn_import_landed_cost_count = len(costs)

    def action_view_gn_import_landed_costs(self):
        self.ensure_one()
        costs = self.gn_import_landed_cost_ids
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Costos en destino'),
            'res_model': 'stock.landed.cost',
            'target': 'current',
        }
        if len(costs) == 1:
            action.update({'view_mode': 'form', 'res_id': costs.id})
        else:
            action.update({
                'view_mode': 'list,form',
                'domain': [('id', 'in', costs.ids)],
            })
        return action

    def action_gn_import_sync_landed_cost(self):
        """Crea o actualiza un LC borrador con las líneas de gasto del picking.

        Cada picking mantiene sus propias líneas atadas al LC vía
        ``landed_cost_line_id``. Al sincronizar:

        - Si el picking ya está en algún LC borrador vinculado, se reutiliza.
        - Si no, se agrega este picking al primer LC borrador disponible.
        - Si no hay ninguno, se crea uno nuevo.
        """
        self.ensure_one()
        if self.state != 'done':
            raise UserError(_(
                'Solo se pueden sincronizar gastos con costos en destino '
                'sobre recepciones ya validadas.'
            ))
        if not self.gn_import_extra_cost_line_ids:
            raise UserError(_(
                'Registre al menos una línea de gasto adicional antes de '
                'sincronizar.'
            ))

        LandedCost = self.env['stock.landed.cost']
        existing = self.gn_import_landed_cost_ids.filtered(lambda c: c.state == 'draft')
        if existing:
            cost = existing[:1]
        else:
            cost = LandedCost.search([
                ('state', '=', 'draft'),
                ('picking_ids', 'in', self.ids),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
        if not cost:
            new_lines = [
                (0, 0, extra._prepare_cost_line_vals(LandedCost))
                for extra in self.gn_import_extra_cost_line_ids
            ]
            cost = LandedCost.create({
                'picking_ids': [(6, 0, self.ids)],
                'cost_lines': new_lines,
            })
        else:
            if self.id not in cost.picking_ids.ids:
                cost.picking_ids = [(4, self.id)]
            cost_line_cmds = []
            for extra in self.gn_import_extra_cost_line_ids:
                vals = extra._prepare_cost_line_vals(cost)
                if extra.landed_cost_line_id:
                    cost_line_cmds.append((1, extra.landed_cost_line_id.id, vals))
                else:
                    cost_line_cmds.append((0, 0, vals))
            cost.with_context(skip_cost_lines_check=True).write({
                'cost_lines': cost_line_cmds,
            })

        # Asigna referencias a las líneas recién creadas (mismo orden que se
        # enviaron, único método fiable con comandos (0,0,...)).
        pending = self.gn_import_extra_cost_line_ids.filtered(
            lambda l: not l.landed_cost_line_id
        )
        if pending:
            new_lines = cost.cost_lines.filtered(
                lambda l: l.expense_scope == 'picking' and l.picking_id == self
            ).sorted(key=lambda l: l.id, reverse=True)[:len(pending)]
            for extra, line in zip(pending, reversed(new_lines)):
                extra.landed_cost_line_id = line.id

        return {
            'type': 'ir.actions.act_window',
            'name': _('Costo en destino'),
            'res_model': 'stock.landed.cost',
            'res_id': cost.id,
            'view_mode': 'form',
            'target': 'current',
        }


class GnImportExtraCostLine(models.Model):
    _name = 'gn.import.extra.cost.line'
    _description = 'Gasto adicional de importación por picking'

    picking_id = fields.Many2one(
        'stock.picking', required=True, ondelete='cascade', index=True,
    )
    expense_type = fields.Selection(
        [
            ('import_permit', 'Permisos de importación'),
            ('import_duty', 'Derechos arancelarios'),
            ('import_production_tax', 'Impuesto por producción'),
            ('other', 'Otro'),
        ],
        string='Tipo',
        required=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        domain=[('landed_cost_ok', '=', True)],
    )
    name = fields.Char(string='Descripción')
    amount = fields.Monetary(string='Monto', required=True)
    currency_id = fields.Many2one(
        'res.currency',
        related='picking_id.company_id.currency_id',
        readonly=True,
    )
    split_method = fields.Selection(
        [
            ('equal', 'Equitativo'),
            ('by_quantity', 'Por cantidad'),
            ('by_weight', 'Por peso'),
            ('by_volume', 'Por volumen'),
            ('by_current_cost_price', 'Por costo actual'),
        ],
        default='by_quantity',
        required=True,
        string='Método de reparto',
    )
    vendor_bill_id = fields.Many2one(
        'account.move',
        string='Factura de gasto',
        domain=[('move_type', '=', 'in_invoice')],
    )
    landed_cost_line_id = fields.Many2one(
        'stock.landed.cost.lines',
        string='Línea de costo en destino',
        readonly=True,
        copy=False,
        ondelete='set null',
    )

    @api.onchange('expense_type')
    def _onchange_expense_type(self):
        mapping = {
            'import_permit': 'gn_import_landed_cost.product_import_permit',
            'import_duty': 'gn_import_landed_cost.product_import_duty',
            'import_production_tax':
                'gn_import_landed_cost.product_import_production_tax',
        }
        xmlid = mapping.get(self.expense_type)
        if xmlid:
            self.product_id = self.env.ref(xmlid, raise_if_not_found=False)

    def _prepare_cost_line_vals(self, cost):
        """Diccionario de valores para crear/actualizar la línea de LC.

        ``invoice_amount_lc`` se replica desde ``amount`` porque
        ``invoice_in_landed_cost`` recomputa el ``price_unit`` de cada línea
        a partir de la factura (base en moneda de la línea). Sin este valor
        el price_unit termina en cero al persistir.
        """
        self.ensure_one()
        return {
            'name': self.name or self.product_id.display_name,
            'product_id': self.product_id.id,
            'price_unit': self.amount,
            'invoice_amount_lc': self.amount,
            'split_method': self.split_method,
            'expense_scope': 'picking',
            'picking_id': self.picking_id.id,
            'account_id': cost._get_cost_line_account(self.product_id) if hasattr(cost, '_get_cost_line_account') else False,
            'vendor_bill_id_lc': self.vendor_bill_id.id or False,
            'vendor_id_lc': self.vendor_bill_id.partner_id.id if self.vendor_bill_id else False,
        }
