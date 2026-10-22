# -*- coding: utf-8 -*-

from odoo import _, api, models
from odoo.exceptions import ValidationError


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.constrains('group_ids')
    def _check_gn_contact_manager_exclusive(self):
        readonly = self.env.ref(
            'gn_permissions.group_contact_manager_readonly', raise_if_not_found=False
        )
        editor = self.env.ref(
            'gn_permissions.group_contact_manager_editor', raise_if_not_found=False
        )
        if not readonly or not editor:
            return
        for user in self:
            if readonly in user.group_ids and editor in user.group_ids:
                raise ValidationError(
                    _(
                        'No puede asignar a la vez los grupos «Gestor de contactos - Solo lectura» '
                        'y «Gestor de contactos - Puede crear/editar» al usuario %s.'
                    )
                    % (user.display_name,)
                )
