# -*- coding: utf-8 -*-
"""Marca como desinstalados módulos que ya no están en el addons-path de Grupohmm.

Evita el ERROR al cargar el registro: «Some modules are not loaded» cuando en BD siguen
en estado instalado `form_full_screen` o `gn_hr_driver_license` (retirados / no incluidos
en el path de producción).
"""
import logging

_logger = logging.getLogger(__name__)

_PHANTOM = ("form_full_screen", "gn_hr_driver_license")


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        DELETE FROM ir_module_module_dependency
        WHERE name IN %s
        """,
        (_PHANTOM,),
    )
    dep_removed = cr.rowcount
    cr.execute(
        """
        UPDATE ir_module_module
        SET state = 'uninstalled'
        WHERE name IN %s
          AND state != 'uninstalled'
        """,
        (_PHANTOM,),
    )
    n = cr.rowcount
    if dep_removed or n:
        _logger.info(
            "l10n_hn_hr_payroll 19.0.1.0.47 post-migrate: phantom modules → uninstalled "
            "(%s rows), dependency rows removed: %s",
            n,
            dep_removed,
        )
