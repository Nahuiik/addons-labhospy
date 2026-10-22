# -*- coding: utf-8 -*-
"""Copia referencias de hr_employee_reference → reference.personal antes de eliminar el modelo."""


def migrate(cr, version):
    cr.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'hr_employee_reference'
        )
        """
    )
    if not cr.fetchone()[0]:
        return
    cr.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'reference_personal'
        )
        """
    )
    if not cr.fetchone()[0]:
        return

    cr.execute(
        """
        INSERT INTO reference_personal (
            employee_id, name, address, phone, occupation, time,
            create_uid, create_date, write_uid, write_date, applicant_id
        )
        SELECT
            r.employee_id,
            r.name,
            NULLIF(TRIM(BOTH FROM COALESCE(r.notes, '')), ''),
            NULLIF(TRIM(BOTH FROM COALESCE(r.phone, '')), ''),
            CASE
                WHEN r.reference_type = 'work' THEN
                    CASE
                        WHEN r.relation_company IS NOT NULL
                            AND TRIM(BOTH FROM r.relation_company) != ''
                        THEN 'Laboral: ' || r.relation_company
                        ELSE 'Laboral'
                    END
                WHEN r.reference_type = 'personal' THEN
                    CASE
                        WHEN r.relation_company IS NOT NULL
                            AND TRIM(BOTH FROM r.relation_company) != ''
                        THEN 'Personal: ' || r.relation_company
                        ELSE 'Personal'
                    END
                ELSE COALESCE(r.relation_company, '')
            END,
            r.time_known,
            r.create_uid,
            r.create_date,
            r.write_uid,
            r.write_date,
            NULL
        FROM hr_employee_reference r
        WHERE r.employee_id IS NOT NULL
        """
    )
