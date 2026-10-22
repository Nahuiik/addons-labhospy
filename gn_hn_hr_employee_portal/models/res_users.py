# -*- coding: utf-8 -*-

from odoo import models


class ResUsers(models.Model):
    _inherit = "res.users"
    _mailing_enabled = True
