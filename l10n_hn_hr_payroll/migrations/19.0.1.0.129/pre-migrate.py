# -*- coding: utf-8 -*-
"""Renombra columnas de período de prueba HN a nombres por localización."""


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'res_company' AND column_name = 'trial_period_days'
        """
    )
    if cr.fetchone():
        cr.execute(
            "ALTER TABLE res_company RENAME COLUMN trial_period_days TO l10n_hn_trial_period_days"
        )
