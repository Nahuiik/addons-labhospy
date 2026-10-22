# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class AccountMove(models.Model):
    _inherit = 'account.move'

    gn_can_edit_payment_terms = fields.Boolean(
        compute='_compute_gn_can_edit_payment_terms',
        string='Puede editar términos de pago',
    )

    @api.depends_context('uid')
    def _compute_gn_can_edit_payment_terms(self):
        can_edit = self._gn_can_edit_payment_terms()
        for move in self:
            move.gn_can_edit_payment_terms = can_edit

    def _gn_can_edit_payment_terms(self):
        return self.env.su or self.env.user.has_group(
            'gn_permissions.group_payment_terms_edit'
        )

    @api.model_create_multi
    def create(self, vals_list):
        if not self._gn_can_edit_payment_terms():
            for vals in vals_list:
                vals.pop('invoice_payment_term_id', None)
        return super().create(vals_list)

    def write(self, vals):
        if not self._gn_can_edit_payment_terms() and 'invoice_payment_term_id' in vals:
            raise AccessError(
                _(
                    'No puede modificar términos de pago: necesita el permiso '
                    '«Puede modificar términos de pago».'
                )
            )
        return super().write(vals)
