# -*- coding: utf-8 -*-
"""
Clean up M2M orphans (sport/surgery/disease/medication) that reference old
comodels, and handle reference_ids → hn_reference_ids rename on hr.employee.
"""


def _table_exists(cr, name):
    cr.execute("SELECT to_regclass(%s)", (name,))
    return cr.fetchone()[0] is not None


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    return cr.fetchone() is not None


def _delete_orphans(cr, rel_table, fk_column, target_table):
    if not _table_exists(cr, rel_table):
        return
    if _table_exists(cr, target_table):
        cr.execute(
            """
            DELETE FROM {rel} AS r
            WHERE NOT EXISTS (
                SELECT 1 FROM {tgt} AS t WHERE t.id = r.{fk}
            )
            """.format(rel=rel_table, tgt=target_table, fk=fk_column)
        )
    else:
        cr.execute("DELETE FROM {}".format(rel_table))


def migrate(cr, version):
    # --- M2M orphan cleanup (same as previous migrations) ---
    pairs = (
        ("hr_employee_sport_rel", "sport_id", "l10n_hn_hr_recruitment_sports"),
        ("hr_employee_surgery_rel", "surgery_id", "l10n_hn_hr_recruitment_surgire"),
        ("hr_employee_disease_rel", "disease_id", "l10n_hn_hr_recruitment_diseases"),
        ("hr_employee_medication_rel", "medication_id", "l10n_hn_hr_recruitment_medication"),
    )
    for rel_table, fk_column, target_table in pairs:
        _delete_orphans(cr, rel_table, fk_column, target_table)
