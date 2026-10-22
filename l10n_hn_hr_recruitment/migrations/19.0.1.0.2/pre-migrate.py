# -*- coding: utf-8 -*-
"""
Remove M2M rows that still reference old comodels (e.g. hr_sport) so Odoo can
attach FKs to l10n_hn_hr_recruitment.* tables without integrity errors.
"""


def _table_exists(cr, name):
    cr.execute(
        "SELECT to_regclass(%s)",
        (name,),
    )
    return cr.fetchone()[0] is not None


def _delete_orphans(cr, rel_table, fk_column, target_table):
    if not _table_exists(cr, rel_table):
        return
    # Identifier whitelist only (no user input).
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
        # Target table not created yet: rel still points at old comodel (e.g. hr_sport).
        # Clear links so the new FK to l10n_hn_hr_recruitment.* can be applied.
        cr.execute("DELETE FROM {}".format(rel_table))


def migrate(cr, version):
    pairs = (
        ("hr_employee_sport_rel", "sport_id", "l10n_hn_hr_recruitment_sports"),
        ("hr_employee_surgery_rel", "surgery_id", "l10n_hn_hr_recruitment_surgire"),
        ("hr_employee_disease_rel", "disease_id", "l10n_hn_hr_recruitment_diseases"),
        ("hr_employee_medication_rel", "medication_id", "l10n_hn_hr_recruitment_medication"),
    )
    for rel_table, fk_column, target_table in pairs:
        _delete_orphans(cr, rel_table, fk_column, target_table)
