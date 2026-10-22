# -*- coding: utf-8 -*-
"""Copia enfermedades desde la relación M2M respaldada a hr.employee.chronic.disease.line."""


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_name = '_migrate_hr_employee_disease_rel'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'hr_employee_chronic_disease_line'
        """
    )
    if not cr.fetchone():
        cr.execute("DROP TABLE IF EXISTS _migrate_hr_employee_disease_rel")
        return
    cr.execute(
        """
        INSERT INTO hr_employee_chronic_disease_line (
            employee_id, disease_id, disease_date, under_treatment, treatment_place,
            create_uid, create_date, write_uid, write_date
        )
        SELECT
            b.employee_id,
            b.disease_id,
            NULL::date,
            false,
            NULL::varchar,
            1,
            NOW() AT TIME ZONE 'UTC',
            1,
            NOW() AT TIME ZONE 'UTC'
        FROM _migrate_hr_employee_disease_rel b
        INNER JOIN hr_employee e ON e.id = b.employee_id
        INNER JOIN hr_disease d ON d.id = b.disease_id
        WHERE NOT EXISTS (
            SELECT 1 FROM hr_employee_chronic_disease_line l
            WHERE l.employee_id = b.employee_id AND l.disease_id = b.disease_id
        )
        """
    )
    cr.execute("DROP TABLE IF EXISTS _migrate_hr_employee_disease_rel")
