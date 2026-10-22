# -*- coding: utf-8 -*-

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.gn_consume_product.hooks import sync_consume_sequences

    sync_consume_sequences(env)
