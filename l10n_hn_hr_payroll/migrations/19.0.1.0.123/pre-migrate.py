# -*- coding: utf-8 -*-
"""Respaldo de relación M2M parientes en empresa antes de sustituirla por líneas One2many."""


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'hr_employee_relative_colleague_rel'
        """
    )
    if not cr.fetchone():
        return
    cr.execute("DROP TABLE IF EXISTS _hr_employee_relative_colleague_rel_backup")
    cr.execute(
        """
        CREATE TABLE _hr_employee_relative_colleague_rel_backup AS
        SELECT employee_id, colleague_employee_id
        FROM hr_employee_relative_colleague_rel
        """
    )
