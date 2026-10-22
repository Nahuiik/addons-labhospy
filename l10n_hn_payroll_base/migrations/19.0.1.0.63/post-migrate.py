# -*- coding: utf-8 -*-
"""Marca noupdate en alias group_hr_payroll_* (ver hooks._sync_payroll_compat_group_xmlids)."""
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.l10n_hn_payroll_base import hooks

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    hooks._sync_payroll_compat_group_xmlids(env)
    _logger.info(
        "l10n_hn_payroll_base 19.0.1.0.63: XML-IDs Enterprise noupdate + resync",
    )
