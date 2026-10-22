# -*- coding: utf-8 -*-
from odoo import fields, models


class Users(models.Model):
    """ Inherit and adding some fields to the 'res.users'"""
    _inherit = "res.users"

    def invalidate_session(self):
        for user in self:
            params = {"type": "custom-logout", "payload": {"user_id": user.id}}
            self.env["bus.bus"]._sendone("custom-logout","notification",params)
