# -*- coding: utf-8 -*-
# Migración: Líneas de planilla - añadir employee_id y rellenar desde version_id.
# Se ejecuta ANTES de cargar el modelo para que employee_id exista y tenga datos
# cuando el compute de version_id dependa de él.

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Añadir columna employee_id si no existe y rellenar desde version_id."""
    tables = [
        'l10n_hn_payroll_line_he',
        'l10n_hn_payroll_line_te',
        'l10n_hn_payroll_line_bd',
    ]
    for table in tables:
        cr.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
            (table,),
        )
        if not cr.fetchone():
            _logger.info("Table %s does not exist yet, skipping", table)
            continue
        cr.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = %s AND column_name = 'employee_id'
            """,
            (table,),
        )
        if cr.fetchone():
            _logger.info("Column employee_id already exists in %s", table)
            continue
        cr.execute(
            f'ALTER TABLE "{table}" ADD COLUMN employee_id INTEGER REFERENCES hr_employee(id) ON DELETE CASCADE'
        )
        cr.execute(
            f"""
            UPDATE "{table}" SET employee_id = v.employee_id
            FROM hr_version v
            WHERE "{table}".version_id = v.id
            """
        )
        _logger.info("Migrated employee_id for %s", table)
