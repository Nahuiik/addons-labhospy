# -*- coding: utf-8 -*-
"""Marca plantillas de planilla HN: is_template (company_id obligatorio; no usar NULL)."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE hr_employee_recurring_concept
        SET is_template = TRUE
        WHERE employee_id IS NULL
          AND code IN (
              'PREST_PERS',
              'BONO_PROD',
              'BONO_TRANS',
              'BONO_ALIM',
              'CUOTA_SIND',
              'OTROS_PLANILLA',
              'IIHSS'
          )
        """
    )
