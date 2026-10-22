# -*- coding: utf-8 -*-
"""Asignar country_id Honduras a las estructuras estándar HN (Fase 1 plan multi-país).

Los registros creados antes de 19.0.1.0.40 pueden tener country_id vacío o el de la
compañía al instalar; se normalizan vía XML IDs del módulo.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

_STRUCTURE_XMLIDS = (
    'l10n_hn_hr_payroll.structure_biweekly',
    'l10n_hn_hr_payroll.structure_monthly',
    'l10n_hn_hr_payroll.structure_13th_month',
    'l10n_hn_hr_payroll.structure_14th_month',
)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    country = env.ref('base.hn', raise_if_not_found=False)
    if not country:
        _logger.warning('post-migrate 19.0.1.0.40: base.hn no encontrado, se omite country_id en estructuras')
        return
    Structure = env['hr.payroll.structure']
    updated = 0
    for xid in _STRUCTURE_XMLIDS:
        rec = env.ref(xid, raise_if_not_found=False)
        if not rec or rec._name != 'hr.payroll.structure':
            continue
        if rec.country_id != country:
            rec.write({'country_id': country.id})
            updated += 1
    if updated:
        _logger.info(
            'post-migrate 19.0.1.0.40: country_id=HN en %s estructura(s) de nómina',
            updated,
        )
