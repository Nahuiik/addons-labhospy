from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    gn_labhospy_immediate_payment = fields.Boolean(
        string='Pago Inmediato',
        default=False,
        copy=False,
        help='Activa los términos de pago «Pago inmediato». Al desactivar, '
             'restaura el término que tenía la orden antes de activarlo.',
    )
    gn_labhospy_payment_term_before_immediate = fields.Many2one(
        comodel_name='account.payment.term',
        string='Término de pago anterior',
        copy=False,
        help='Término de pago guardado al activar Pago Inmediato.',
    )
    gn_labhospy_has_invoice = fields.Boolean(
        string='Tiene factura',
        compute='_compute_gn_labhospy_has_invoice',
        help='True si la orden ya tiene al menos una factura de cliente vinculada.',
    )

    gn_labhospy_has_controlled_products = fields.Boolean(
        string='Tiene productos controlados (LabHosPy)',
        compute='_compute_gn_labhospy_has_controlled_products',
        help='True si alguna línea de producto tiene plantilla marcada como controlada.',
    )
    gn_labhospy_order_contact_display = fields.Char(
        string='Contacto',
        compute='_compute_gn_labhospy_order_contact_display',
        help='Nombre de contacto según facturación o contactos de la empresa.',
    )

    @api.depends(
        'order_line',
        'order_line.display_type',
        'order_line.product_id',
        'order_line.product_template_id.gn_labhospy_is_controlled',
    )
    def _compute_gn_labhospy_has_controlled_products(self):
        for order in self:
            order.gn_labhospy_has_controlled_products = any(
                not line.display_type
                and line.product_id
                and line.product_id.product_tmpl_id.gn_labhospy_is_controlled
                for line in order.order_line
            )

    @api.depends('partner_id', 'partner_invoice_id')
    def _compute_gn_labhospy_order_contact_display(self):
        for order in self:
            if not order.partner_id:
                order.gn_labhospy_order_contact_display = False
                continue
            inv = order.partner_invoice_id
            if inv and inv != order.partner_id:
                name = inv.name
            elif not order.partner_id.is_company:
                name = order.partner_id.name
            else:
                contacts = order.partner_id.child_ids.filtered(
                    lambda p: p.type == 'contact' and p.active
                )
                name = contacts[:1].name or ''
            order.gn_labhospy_order_contact_display = name or False

    @api.depends('invoice_ids', 'invoice_ids.state', 'invoice_ids.move_type')
    def _compute_gn_labhospy_has_invoice(self):
        for order in self:
            order.gn_labhospy_has_invoice = bool(order.invoice_ids.filtered(
                lambda move: move.move_type in ('out_invoice', 'out_refund')
                and move.state != 'cancel'
            ))

    def _gn_labhospy_check_immediate_payment_editable(self):
        blocked = self.filtered('gn_labhospy_has_invoice')
        if blocked:
            raise UserError(_(
                'No puede modificar «Pago Inmediato» porque ya existe una factura '
                'vinculada a esta orden de venta.'
            ))

    @api.model
    def _gn_labhospy_get_immediate_payment_term(self):
        return self.env.ref('account.account_payment_term_immediate', raise_if_not_found=False)

    def _gn_labhospy_apply_immediate_payment(self, enable):
        """Aplica o revierte término Pago inmediato sobre registros en memoria."""
        self.ensure_one()
        immediate = self._gn_labhospy_get_immediate_payment_term()
        if not immediate:
            return
        if enable:
            if self.payment_term_id != immediate:
                self.gn_labhospy_payment_term_before_immediate = self.payment_term_id
                self.payment_term_id = immediate
        else:
            restore = self.gn_labhospy_payment_term_before_immediate
            if not restore and self.partner_id:
                restore = self.partner_id.property_payment_term_id
            self.payment_term_id = restore
            self.gn_labhospy_payment_term_before_immediate = False

    def _gn_labhospy_prepare_immediate_payment_vals(self, vals):
        """Enriquece vals al guardar el toggle Pago Inmediato."""
        if 'gn_labhospy_immediate_payment' not in vals:
            return vals, False

        immediate = self._gn_labhospy_get_immediate_payment_term()
        if not immediate:
            return vals, False

        enable = vals['gn_labhospy_immediate_payment']
        if len(self) != 1:
            return vals, False

        order = self
        result = dict(vals)
        if enable:
            if order.payment_term_id != immediate:
                if 'gn_labhospy_payment_term_before_immediate' not in result:
                    result['gn_labhospy_payment_term_before_immediate'] = order.payment_term_id.id
            result['payment_term_id'] = immediate.id
        else:
            restore = order.gn_labhospy_payment_term_before_immediate
            if not restore and order.partner_id:
                restore = order.partner_id.property_payment_term_id
            result['payment_term_id'] = restore.id if restore else False
            result['gn_labhospy_payment_term_before_immediate'] = False
        return result, True

    def _gn_labhospy_check_manual_payment_term_change(self, vals):
        """Bloquea cambios manuales del término sin permiso (excepto vía toggle)."""
        if 'payment_term_id' not in vals or self.env.context.get(
            'gn_labhospy_skip_payment_term_guard'
        ):
            return
        if hasattr(self, '_gn_can_edit_payment_terms') and self._gn_can_edit_payment_terms():
            immediate = self._gn_labhospy_get_immediate_payment_term()
            for order in self:
                if order.gn_labhospy_immediate_payment and immediate:
                    if vals.get('payment_term_id') != immediate.id:
                        raise AccessError(_(
                            'No puede cambiar el término de pago mientras '
                            '«Pago Inmediato» está activo. Desactive el toggle primero.'
                        ))
            return
        raise AccessError(_(
            'No puede modificar términos de pago: necesita el permiso '
            '«Puede modificar términos de pago» o use el toggle «Pago Inmediato».'
        ))

    @api.onchange('gn_labhospy_immediate_payment')
    def _onchange_gn_labhospy_immediate_payment(self):
        for order in self:
            order._gn_labhospy_apply_immediate_payment(order.gn_labhospy_immediate_payment)

    @api.onchange('payment_term_id')
    def _onchange_payment_term_id_labhospy_immediate(self):
        immediate = self._gn_labhospy_get_immediate_payment_term()
        if not immediate:
            return
        for order in self:
            if order.payment_term_id == immediate:
                order.gn_labhospy_immediate_payment = True
            elif order.gn_labhospy_immediate_payment:
                order.gn_labhospy_immediate_payment = False

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        skip_guard = False
        for vals in vals_list:
            item = dict(vals)
            if item.get('gn_labhospy_immediate_payment'):
                immediate = self._gn_labhospy_get_immediate_payment_term()
                if immediate:
                    if not item.get('gn_labhospy_payment_term_before_immediate'):
                        partner = self.env['res.partner'].browse(item.get('partner_id'))
                        previous = item.get('payment_term_id') or (
                            partner.property_payment_term_id.id if partner else False
                        )
                        if previous and previous != immediate.id:
                            item['gn_labhospy_payment_term_before_immediate'] = previous
                    item['payment_term_id'] = immediate.id
                    skip_guard = True
            prepared.append(item)
        ctx = dict(self.env.context)
        if skip_guard:
            ctx['gn_labhospy_skip_payment_term_guard'] = True
        return super(SaleOrder, self.with_context(**ctx)).create(prepared)

    def write(self, vals):
        if 'gn_labhospy_immediate_payment' in vals:
            self._gn_labhospy_check_immediate_payment_editable()
        vals, skip_guard = self._gn_labhospy_prepare_immediate_payment_vals(vals)
        if skip_guard:
            return super(
                SaleOrder,
                self.with_context(gn_labhospy_skip_payment_term_guard=True),
            ).write(vals)
        self._gn_labhospy_check_manual_payment_term_change(vals)
        return super().write(vals)
