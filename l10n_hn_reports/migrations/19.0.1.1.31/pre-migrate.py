# -*- coding: utf-8 -*-
"""Si res_company carece de columnas de l10n_hn_reports, el ORM falla al leer compañías (upgrade/install)."""


def migrate(cr, version):
    cols = (
        'hn_isv_closing_journal_id',
        'hn_isv_closing_debit_account_id',
        'hn_isv_closing_credit_account_id',
    )
    for col in cols:
        cr.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'res_company'
              AND column_name = %s
            """,
            (col,),
        )
        if cr.fetchone():
            continue
        # Sin FK aquí: evita errores si el orden de módulos varía; Odoo alinea en el update del módulo.
        cr.execute(
            'ALTER TABLE res_company ADD COLUMN %s INTEGER NULL' % col
        )

    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_name = 'res_company_hn_isr_report_account_rel'
        """
    )
    if not cr.fetchone():
        cr.execute(
            """
            CREATE TABLE res_company_hn_isr_report_account_rel (
                company_id INTEGER NOT NULL
                    REFERENCES res_company(id) ON DELETE CASCADE,
                account_id INTEGER NOT NULL
                    REFERENCES account_account(id) ON DELETE CASCADE,
                CONSTRAINT res_company_hn_isr_report_account_rel_uniq
                    UNIQUE (company_id, account_id)
            )
            """
        )
