# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class ResUser(models.Model):
    _inherit = 'res.users'

    read_only = fields.Boolean(
        string='Make Read Only',
        compute='_compute_read_only',
        help='Whether the user has the Read Only Access group.',
    )

    @api.depends('group_ids')
    def _compute_read_only(self):
        group = self.env.ref(
            'generic_read_only_user_app.group_read_only_user',
            raise_if_not_found=False,
        )
        for user in self:
            user.read_only = bool(group and group in user.group_ids)

    def set_read_only_user(self):
        """Toggle the read-only security group (form button)."""
        self.ensure_one()
        group = self.env.ref('generic_read_only_user_app.group_read_only_user')
        if group in self.group_ids:
            self.sudo().write({'group_ids': [(3, group.id)]})
        else:
            self.sudo().write({'group_ids': [(4, group.id)]})


class IrModelAccess(models.Model):
    _inherit = 'ir.model.access'

    @api.model
    def check(self, model, mode='read', raise_exception=True):
        if self.env.user.has_group('generic_read_only_user_app.group_read_only_user') and mode != 'read':
            if raise_exception:
                raise self._make_access_error(model, mode) from None
            return False
        return super().check(model, mode, raise_exception=raise_exception)


class IrRule(models.Model):
    _inherit = 'ir.rule'

    def _compute_domain(self, model_name: str, mode: str = 'read'):
        skip_models = (
            'res.users.log',
            'res.users',
            'mail.channel',
            'mail.alias',
            'bus.presence',
            'res.lang',
        )
        if model_name not in skip_models and self.env.user.has_group(
            'generic_read_only_user_app.group_read_only_user'
        ) and mode != 'read':
            raise AccessError(
                _('Read only user can not done this operation..! (%s)') % self.env.user.name
            )
        return super()._compute_domain(model_name, mode)
