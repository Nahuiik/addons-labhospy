# -*- coding: utf-8 -*-
"""Migrar parientes en empresa (M2M → líneas) y rellenar company_id en catálogos."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _migrate_in_company_relatives(cr)
    _fill_company_on_hr_catalogs(cr)


def _migrate_in_company_relatives(cr):
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_name = '_hr_employee_relative_colleague_rel_backup'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'hr_employee_in_company_relative'
        """
    )
    if not cr.fetchone():
        cr.execute("DROP TABLE IF EXISTS _hr_employee_relative_colleague_rel_backup")
        return
    cr.execute(
        """
        SELECT id FROM hr_family_relation WHERE active = true ORDER BY id LIMIT 1
        """
    )
    row = cr.fetchone()
    if not row:
        _logger.warning(
            "post-migrate 19.0.1.0.123: sin hr.family.relation activo; "
            "no se migran parientes en empresa desde el respaldo M2M."
        )
        cr.execute("DROP TABLE IF EXISTS _hr_employee_relative_colleague_rel_backup")
        return
    rel_id = row[0]
    cr.execute(
        """
        INSERT INTO hr_employee_in_company_relative
            (employee_id, colleague_id, relation_id, company_id,
             create_uid, create_date, write_uid, write_date)
        SELECT
            r.employee_id,
            r.colleague_employee_id,
            %s,
            COALESCE(e.company_id, (SELECT id FROM res_company ORDER BY id LIMIT 1)),
            COALESCE(e.create_uid, 1),
            NOW() AT TIME ZONE 'UTC',
            COALESCE(e.write_uid, 1),
            NOW() AT TIME ZONE 'UTC'
        FROM _hr_employee_relative_colleague_rel_backup r
        JOIN hr_employee e ON e.id = r.employee_id
        WHERE NOT EXISTS (
            SELECT 1 FROM hr_employee_in_company_relative x
            WHERE x.employee_id = r.employee_id
              AND x.colleague_id = r.colleague_employee_id
        )
        """,
        (rel_id,),
    )
    cr.execute("DROP TABLE IF EXISTS _hr_employee_relative_colleague_rel_backup")
    _logger.info("post-migrate 19.0.1.0.123: parientes en empresa migrados desde M2M.")


def _fill_company_on_hr_catalogs(cr):
    for table in ("hr_project", "hr_assignment"):
        cr.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = %s AND column_name = 'company_id'
            """,
            (table,),
        )
        if not cr.fetchone():
            continue
        cr.execute(
            """
            UPDATE {t}
            SET company_id = (SELECT id FROM res_company ORDER BY id LIMIT 1)
            WHERE company_id IS NULL
            """.format(
                t=table
            )
        )
        _logger.info(
            "post-migrate 19.0.1.0.123: company_id rellenado en %s donde faltaba.",
            table,
        )
