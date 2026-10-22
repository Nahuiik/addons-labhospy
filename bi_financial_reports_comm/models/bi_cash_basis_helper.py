# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

"""Clean-room cash basis balances for financial reports (Odoo 19 community)."""

from odoo import api, fields, models
from odoo.tools.sql import table_columns


class BiCashBasisHelper(models.AbstractModel):
    _name = "bi.cash.basis.helper"
    _description = "Cash basis balance helper for BI financial reports"

    @api.model
    def _temp_table_exists(self):
        self.env.cr.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'bi_cash_basis_temp_aml'
              AND table_schema::regnamespace = pg_my_temp_schema()
            """
        )
        return bool(self.env.cr.fetchone())

    @api.model
    def prepare(self, journal_ids=None):
        """Build temp AML table with payment-weighted amounts (cash basis)."""
        if self._temp_table_exists():
            return

        all_fields = set(table_columns(self.env.cr, "account_move_line"))
        changed_fields = ["date", "amount_currency", "amount_residual", "balance", "debit", "credit"]
        unchanged_fields = list(all_fields - set(changed_fields))
        selected_journals = tuple(journal_ids or [])
        journal_clause = (
            'AND "account_move_line".journal_id IN %(journal_ids)s' if selected_journals else ""
        )

        sql = """
            CREATE TEMPORARY TABLE IF NOT EXISTS bi_cash_basis_temp_aml () INHERITS (account_move_line) ON COMMIT DROP;

            INSERT INTO bi_cash_basis_temp_aml ({all_fields}) SELECT
                {unchanged_fields},
                "account_move_line".date,
                "account_move_line".amount_currency,
                "account_move_line".amount_residual,
                "account_move_line".balance,
                "account_move_line".debit,
                "account_move_line".credit
            FROM ONLY account_move_line
            WHERE (
                "account_move_line".journal_id IN (SELECT id FROM account_journal WHERE type IN ('cash', 'bank'))
                OR "account_move_line".move_id NOT IN (
                    SELECT DISTINCT aml.move_id
                    FROM ONLY account_move_line aml
                    JOIN account_account account ON aml.account_id = account.id
                    WHERE account.account_type IN ('asset_receivable', 'liability_payable')
                )
            )
            {where_journals};

            WITH payment_table AS (
                SELECT
                    aml.move_id,
                    aml.account_id,
                    GREATEST(aml.date, aml2.date) AS date,
                    CASE WHEN (aml.balance = 0 OR sub_aml.total_per_account = 0)
                        THEN 0
                        ELSE part.amount / ABS(sub_aml.total_per_account)
                    END AS matched_percentage,
                    CASE WHEN (aml.balance = 0 OR sub_aml_2.total_per_move = 0)
                        THEN 0
                        ELSE ABS(sub_aml.total_per_account) / ABS(sub_aml_2.total_per_move)
                    END AS move_percentage
                FROM account_partial_reconcile part
                JOIN ONLY account_move_line aml ON aml.id = part.debit_move_id OR aml.id = part.credit_move_id
                JOIN ONLY account_move_line aml2 ON
                    (aml2.id = part.credit_move_id OR aml2.id = part.debit_move_id)
                    AND aml.id != aml2.id
                JOIN (
                    SELECT move_id, account_id, SUM(ABS(balance)) AS total_per_account
                    FROM ONLY account_move_line
                    GROUP BY move_id, account_id
                ) sub_aml ON aml.account_id = sub_aml.account_id AND aml.move_id = sub_aml.move_id
                JOIN (
                    SELECT move_id, SUM(ABS(balance)) AS total_per_move
                    FROM ONLY account_move_line aml_total
                    JOIN account_account account_total ON aml_total.account_id = account_total.id
                    WHERE account_total.account_type IN ('asset_receivable', 'liability_payable')
                    GROUP BY move_id
                ) sub_aml_2 ON aml.move_id = sub_aml_2.move_id
                JOIN account_account account ON aml.account_id = account.id
                WHERE account.account_type IN ('asset_receivable', 'liability_payable')
            )
            INSERT INTO bi_cash_basis_temp_aml ({all_fields}) SELECT
                {unchanged_fields},
                ref.date,
                CASE WHEN account.id = ref.account_id
                    THEN ref.matched_percentage * account_move_line.amount_currency
                    ELSE ref.matched_percentage * account_move_line.amount_currency * ref.move_percentage
                END,
                CASE WHEN account.id = ref.account_id
                    THEN ref.matched_percentage * account_move_line.amount_residual
                    ELSE ref.matched_percentage * account_move_line.amount_residual * ref.move_percentage
                END,
                CASE WHEN account.id = ref.account_id
                    THEN ref.matched_percentage * account_move_line.balance
                    ELSE ref.matched_percentage * account_move_line.balance * ref.move_percentage
                END,
                CASE WHEN account.id = ref.account_id
                    THEN ref.matched_percentage * account_move_line.debit
                    ELSE ref.matched_percentage * account_move_line.debit * ref.move_percentage
                END,
                CASE WHEN account.id = ref.account_id
                    THEN ref.matched_percentage * account_move_line.credit
                    ELSE ref.matched_percentage * account_move_line.credit * ref.move_percentage
                END
            FROM payment_table ref
            JOIN ONLY account_move_line ON account_move_line.move_id = ref.move_id
            JOIN account_account account ON account.id = account_move_line.account_id
            WHERE NOT (
                account_move_line.journal_id IN (SELECT id FROM account_journal WHERE type IN ('cash', 'bank'))
                OR account_move_line.move_id NOT IN (
                    SELECT DISTINCT aml.move_id
                    FROM ONLY account_move_line aml
                    JOIN account_account account ON aml.account_id = account.id
                    WHERE account.account_type IN ('asset_receivable', 'liability_payable')
                )
            )
            AND (account.id = ref.account_id OR account.account_type NOT IN ('asset_receivable', 'liability_payable'))
            {where_journals};

            CREATE INDEX IF NOT EXISTS bi_cash_basis_temp_aml_idx
                ON bi_cash_basis_temp_aml (date, journal_id, company_id, parent_state, account_id);
            ANALYZE bi_cash_basis_temp_aml;
        """.format(
            all_fields=", ".join(f'"{f}"' for f in (unchanged_fields + changed_fields)),
            unchanged_fields=", ".join(f'"account_move_line"."{f}"' for f in unchanged_fields),
            where_journals=journal_clause,
        )
        params = {"journal_ids": selected_journals} if selected_journals else {}
        self.env.cr.execute(sql, params)

    @api.model
    def account_balance(self, account, date_from, date_to, target_move="all", journal_ids=None):
        self.prepare(journal_ids=journal_ids)
        clauses = ["account_id = %s", "company_id = %s"]
        params = [account.id, self.env.company.id]
        if target_move == "posted":
            clauses.append("parent_state = 'posted'")
        else:
            clauses.append("parent_state IN ('draft', 'posted')")
        if date_from:
            clauses.append("date >= %s")
            params.append(date_from)
        if date_to:
            clauses.append("date <= %s")
            params.append(date_to)
        if journal_ids:
            clauses.append("journal_id IN %s")
            params.append(tuple(journal_ids))
        self.env.cr.execute(
            f"SELECT COALESCE(SUM(balance), 0) FROM bi_cash_basis_temp_aml WHERE {' AND '.join(clauses)}",
            params,
        )
        balance = self.env.cr.fetchone()[0] or 0.0
        if account.account_type in ("income", "income_other"):
            return -balance
        return balance
