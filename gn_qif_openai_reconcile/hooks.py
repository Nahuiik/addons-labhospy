# -*- coding: utf-8 -*-
"""Hooks de instalación / diagnóstico."""
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Registra en log si el ORM no expone los campos Nahuiik en `account.reconcile.model`.

    Odoo 19 invoca `post_init_hook` **solo en la primera instalación** del módulo (no en cada `-u`).

    Síntoma típico en cliente: ``field gn_creation_source is undefined`` al abrir la lista
    de modelos de reconciliación: la vista XML ya está en BD pero el Python del módulo
    no se cargó (despliegue incompleto o instancia sin el archivo de modelo).
    """
    if 'account.reconcile.model' not in env:
        return
    Reconcile = env['account.reconcile.model']
    if 'gn_creation_source' not in Reconcile._fields:
        _logger.error(
            'gn_qif_openai_reconcile: el modelo account.reconcile.model no define '
            'gn_creation_source. Revise despliegue de models/account_reconcile_model.py '
            'y ejecute: odoo-bin -u gn_qif_openai_reconcile (véase doc/'
            'TROUBLESHOOTING_GN_CREATION_SOURCE.md).'
        )
    else:
        _logger.info(
            'gn_qif_openai_reconcile: extensión account.reconcile.model (gn_creation_source) registrada.'
        )
