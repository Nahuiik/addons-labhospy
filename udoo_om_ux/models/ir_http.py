# -*- coding: utf-8 -*-
# Copyright 2025 Sveltware Solutions

from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _post_logout(cls):
        super()._post_logout()
        request.future_response.set_cookie('color_scheme', max_age=0)

    def color_scheme(self):
        cookie_scheme = request.httprequest.cookies.get('color_scheme')
        default_scheme = cookie_scheme or super().color_scheme()

        user = request.env.user
        if not user or user._is_public():
            return default_scheme

        user_scheme = user.res_users_settings_id.color_scheme
        return user_scheme if user_scheme in ('light', 'dark') else default_scheme
