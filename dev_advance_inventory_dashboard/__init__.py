# -*- coding: utf-8 -*-
from . import models
from . import report

def pre_init_check(cr):
    from odoo.service import common
    from odoo.exceptions import UserError
    from odoo import _
    version_info = common.exp_version()
    server_serie = version_info.get('server_serie')
    if server_serie != '19.0':
        raise UserError(_(
            "Module does not support Odoo version %s. Expected 19.0") % server_serie)
    return True
