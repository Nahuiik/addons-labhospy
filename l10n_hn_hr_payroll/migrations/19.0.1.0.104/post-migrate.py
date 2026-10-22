# -*- coding: utf-8 -*-
"""Sincronizar traducciones del menú Nómina HN.

Al renombrar el menú en XML, el valor traducido en BD (p. ej. es_GT) puede seguir
siendo «Honduras Payroll Gestión» y la UI lo muestra en lugar del término nuevo.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

_MENU_NAME = 'Nómina HN'


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    menu = env.ref('l10n_hn_hr_payroll.menu_l10n_hn_management', raise_if_not_found=False)
    if not menu:
        return
    langs = env['res.lang'].search([('active', '=', True)])
    for lang in langs:
        menu.with_context(lang=lang.code).write({'name': _MENU_NAME})
    _logger.info(
        'post-migrate 19.0.1.0.104: nombre del menú l10n_hn_hr_payroll.menu_l10n_hn_management '
        'actualizado a %r en %s idioma(s)',
        _MENU_NAME,
        len(langs),
    )
