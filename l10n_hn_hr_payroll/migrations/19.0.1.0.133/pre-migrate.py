# -*- coding: utf-8 -*-
"""
Si aún existe la relación M2M legada (hr_employee_disease_rel), respáldala
antes de cualquier cambio de esquema en esta versión.
Útil cuando una base no pasó por el respaldo de 19.0.1.0.131 o quedó huérfana.
"""


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
