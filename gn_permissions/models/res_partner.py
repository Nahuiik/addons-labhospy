# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

# Campos que otros documentos (ventas, contabilidad) actualizan en automático;
# no equivalen a “editar la ficha del contacto”.
_GN_PARTNER_AUTOWRITE_FIELDS = frozenset({
    'credit_to_invoice',
    'credit',
    'debit',
    'days_sales_outstanding',
    'total_invoiced',
    'customer_rank',
    'supplier_rank',
})

_GN_PARTNER_PAYMENT_TERM_FIELDS = frozenset({
    'property_payment_term_id',
    'property_supplier_payment_term_id',
})


class ResPartner(models.Model):
    _inherit = 'res.partner'

    gn_can_edit_payment_terms = fields.Boolean(
        compute='_compute_gn_can_edit_payment_terms',
        string='Puede editar términos de pago',
    )

    @api.depends_context('uid')
    def _compute_gn_can_edit_payment_terms(self):
        can_edit = self._gn_can_edit_payment_terms()
        for partner in self:
            partner.gn_can_edit_payment_terms = can_edit

    @api.model
    def _gn_immediate_payment_term(self):
        return self.env.ref('account.account_payment_term_immediate', raise_if_not_found=False)

    def _gn_can_edit_payment_terms(self):
        return self.env.su or self.env.user.has_group(
            'gn_permissions.group_payment_terms_edit'
        )

    def _gn_contact_readonly_profile(self):
        """Solo lectura: tiene el grupo readonly y no el de edición."""
        user = self.env.user
        return user.has_group(
            'gn_permissions.group_contact_manager_readonly'
        ) and not user.has_group('gn_permissions.group_contact_manager_editor')

    def _gn_autowrite_only(self, vals):
        if not vals:
            return True
        return set(vals).issubset(_GN_PARTNER_AUTOWRITE_FIELDS)

    @api.model_create_multi
    def create(self, vals_list):
        immediate = self._gn_immediate_payment_term()
        if immediate:
            for vals in vals_list:
                vals['property_payment_term_id'] = immediate.id
                vals['property_supplier_payment_term_id'] = immediate.id
        elif not self._gn_can_edit_payment_terms():
            for vals in vals_list:
                for fname in _GN_PARTNER_PAYMENT_TERM_FIELDS:
                    vals.pop(fname, None)
        if self._gn_contact_readonly_profile():
            raise AccessError(
                _('No puede crear contactos: su usuario tiene el perfil «Gestor de contactos - Solo lectura».')
            )
        return super().create(vals_list)

    def write(self, vals):
        if self.env.su:
            return super().write(vals)
        if not self._gn_can_edit_payment_terms():
            if _GN_PARTNER_PAYMENT_TERM_FIELDS & vals.keys():
                raise AccessError(
                    _(
                        'No puede modificar términos de pago: necesita el permiso '
                        '«Puede modificar términos de pago».'
                    )
                )
        if self.env.context.get('gn_skip_contact_readonly_guard'):
            return super().write(vals)
        if self._gn_contact_readonly_profile():
            if self._gn_autowrite_only(vals):
                return super().write(vals)
            raise AccessError(
                _('No puede modificar contactos: su usuario tiene el perfil «Gestor de contactos - Solo lectura».')
            )
        return super().write(vals)

    def unlink(self):
        if self.env.su:
            return super().unlink()
        if self._gn_contact_readonly_profile():
            raise AccessError(
                _('No puede eliminar contactos: su usuario tiene el perfil «Gestor de contactos - Solo lectura».')
            )
        return super().unlink()
