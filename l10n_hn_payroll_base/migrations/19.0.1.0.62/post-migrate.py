# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.l10n_hn_payroll_base import hooks

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """XML-IDs group_hr_payroll_* (compat Enterprise) en instalaciones ya existentes.

    post_init_hook solo corre en instalación nueva, no en -u. Los alias deben existir
    antes de que addons GN resuelvan ref(...) en datos/vistas.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    hooks._sync_payroll_compat_group_xmlids(env)
    _logger.info("l10n_hn_payroll_base: sincronizados XML-IDs group_hr_payroll_* → group_hn_*")
