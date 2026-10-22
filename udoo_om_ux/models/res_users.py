# -*- coding: utf-8 -*-
# Copyright 2025 Sveltware Solutions

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    color_scheme = fields.Selection(related='res_users_settings_id.color_scheme', readonly=False)

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['color_scheme']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['color_scheme']

    def _swclang(self):
        if lang := self.env.context.get('clang'):
            self.env.user.lang = lang
        return {
            'type': 'ir.actions.client',
            'tag': 'reload_context',
        }


class ResUsersSettings(models.Model):
    _inherit = 'res.users.settings'

    ps_data = fields.Serialized()
    ps_start_xmlid = fields.Char(sparse='ps_data')
    ps_menu_orders = fields.Json(sparse='ps_data')
    ps_fav_menus = fields.Json(sparse='ps_data')
    ps_auto_hmenu = fields.Selection([('on', 'On'), ('off', 'Off')], sparse='ps_data')
    ps_full_iland = fields.Selection([('on', 'On'), ('off', 'Off')], sparse='ps_data')

    up_bookmarks = fields.Json(readonly=True)

    color_scheme = fields.Selection(
        [('system', 'System'), ('light', 'Light'), ('dark', 'Dark')],
        default='system',
        required=True,
        string='Color Scheme',
    )
