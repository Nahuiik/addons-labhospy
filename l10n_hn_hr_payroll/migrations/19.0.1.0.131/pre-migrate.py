# -*- coding: utf-8 -*-
"""Respalda la relación M2M hr.disease antes de sustituirla por líneas One2many."""


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'hr_employee_disease_rel'
        """
    )
    if not cr.fetchone():
        return
    cr.execute("DROP TABLE IF EXISTS _migrate_hr_employee_disease_rel")
    cr.execute(
        """
        CREATE TABLE _migrate_hr_employee_disease_rel AS
        SELECT * FROM hr_employee_disease_rel
        """
    )
