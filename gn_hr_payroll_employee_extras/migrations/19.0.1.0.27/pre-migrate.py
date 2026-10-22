# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# Antes del ORM: copia reparto por pesos al nuevo monto explícito de 1.ª quincena.


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'hr_employee_recurring_concept'
          AND column_name = 'loan_quota_biweek_weight_first'
        """
    )
    if not cr.fetchone():
        return

    cr.execute(
        """
        ALTER TABLE hr_employee_recurring_concept
        ADD COLUMN IF NOT EXISTS loan_first_biweek_amount double precision
        DEFAULT 0;
        """
    )

    cr.execute(
        """
        UPDATE hr_employee_recurring_concept
        SET loan_first_biweek_amount = ROUND(
            (COALESCE(amount, 0) * COALESCE(loan_quota_biweek_weight_first, 0))
            / NULLIF(
                COALESCE(loan_quota_biweek_weight_first, 0)
                + COALESCE(loan_quota_biweek_weight_second, 0),
                0
              ),
            2
        )
        WHERE loan_split_quota_across_biweeks IS TRUE
          AND amount_type = 'fixed'
          AND (
            COALESCE(loan_quota_biweek_weight_first, 0)
            + COALESCE(loan_quota_biweek_weight_second, 0)
          ) > 0;
        """
    )
