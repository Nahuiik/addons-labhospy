# -*- coding: utf-8 -*-
"""
Importa enfermedades a hr_employee_chronic_disease_line desde:
- hr_employee_disease_rel (M2M antigua "Enfermedades que sufre"), si la tabla sigue existiendo
- _migrate_hr_employee_disease_rel (respaldo de pre-migrate 131 o 133)

Solo crea filas que aún no existan (mismo employee_id + disease_id). Valida FK a empleado y catálogo.
"""


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'hr_employee_chronic_disease_line'
        """
    )
    if not cr.fetchone():
        return

    sources = ("hr_employee_disease_rel", "_migrate_hr_employee_disease_rel")
    for table in sources:
        cr.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_name = %s
            """,
            (table,),
        )
        if not cr.fetchone():
            continue
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
            FROM """
            + table
            + """ b
            INNER JOIN hr_employee e ON e.id = b.employee_id
            INNER JOIN hr_disease d ON d.id = b.disease_id
            WHERE NOT EXISTS (
                SELECT 1 FROM hr_employee_chronic_disease_line l
                WHERE l.employee_id = b.employee_id AND l.disease_id = b.disease_id
            )
            """
        )

    cr.execute("DROP TABLE IF EXISTS _migrate_hr_employee_disease_rel")
