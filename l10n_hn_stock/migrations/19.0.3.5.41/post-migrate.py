# -*- coding: utf-8 -*-
"""Elimina xmlids de secuencias consumo/entrante ya centralizadas en gn_consume_product."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        from odoo.addons.gn_consume_product.hooks import (
            cleanup_l10n_duplicate_consume_sequences,
        )
    except ImportError:
        return
    cleanup_l10n_duplicate_consume_sequences(env)
