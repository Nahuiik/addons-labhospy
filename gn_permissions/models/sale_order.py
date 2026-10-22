# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    gn_can_edit_payment_terms = fields.Boolean(
        compute='_compute_gn_can_edit_payment_terms',
        string='Puede editar términos de pago',
    )

    @api.depends_context('uid')
    def _compute_gn_can_edit_payment_terms(self):
        can_edit = self._gn_can_edit_payment_terms()
        for order in self:
            order.gn_can_edit_payment_terms = can_edit

    def _gn_can_edit_payment_terms(self):
        return self.env.su or self.env.user.has_group(
            'gn_permissions.group_payment_terms_edit'
        )

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('gn_labhospy_skip_payment_term_guard'):
            return super().create(vals_list)
        if not self._gn_can_edit_payment_terms():
            for vals in vals_list:
                vals.pop('payment_term_id', None)
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get('gn_labhospy_skip_payment_term_guard'):
            return super().write(vals)
        if not self._gn_can_edit_payment_terms() and 'payment_term_id' in vals:
            raise AccessError(
                _(
                    'No puede modificar términos de pago: necesita el permiso '
                    '«Puede modificar términos de pago».'
                )
            )
        return super().write(vals)

    def action_confirm(self):
        # La confirmación recalcula crédito/márgenes en partner; no es edición manual de la ficha.
        return super(
            SaleOrder,
            self.with_context(gn_skip_contact_readonly_guard=True),
        ).action_confirm()
