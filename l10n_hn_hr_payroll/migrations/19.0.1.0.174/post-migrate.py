# -*- coding: utf-8 -*-
"""Idempotente: misma lógica que pre-migrate 19.0.1.0.176 por bases que solo pasaron por 174."""


def _dedupe_config_parameters(cr):
    cr.execute(
        """
        DELETE FROM ir_config_parameter AS p
        USING ir_config_parameter AS q
        WHERE p.key LIKE 'gn_hn_hr_vacation.%%'
          AND q.key = 'l10n_hn_hr_payroll' || substring(p.key FROM length('gn_hn_hr_vacation') + 1)
        """
    )


def migrate(cr, version):
    cr.execute(
        """
        DELETE FROM ir_model_data AS imd
        USING ir_model_data AS other
        WHERE imd.module = 'gn_hn_hr_vacation'
          AND other.module = 'l10n_hn_hr_payroll'
          AND other.name = imd.name
        """
    )
    cr.execute(
        """
        UPDATE ir_model_data
        SET module = 'l10n_hn_hr_payroll'
        WHERE module = 'gn_hn_hr_vacation'
        """
    )
    _dedupe_config_parameters(cr)
    cr.execute(
        """
        UPDATE ir_config_parameter
        SET key = 'l10n_hn_hr_payroll' || substring(key FROM length('gn_hn_hr_vacation') + 1)
        WHERE key LIKE 'gn_hn_hr_vacation.%%'
        """
    )
