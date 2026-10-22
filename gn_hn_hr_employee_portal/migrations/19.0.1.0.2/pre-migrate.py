# -*- coding: utf-8 -*-
"""
Migración: gn.hr.work.certificate.type -> hr.work.certificate.type

Actualiza las solicitudes de constancia para usar hr.work.certificate.type
en lugar del modelo eliminado gn.hr.work.certificate.type.
Mapea por código y marca for_portal=True. Si el tipo no existe, lo crea.
"""
import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)

# Mapeo código antiguo -> (código nuevo, nombre) para gn_hr_documents
# Si el código nuevo no existe, se crea con estos datos
CODE_MAP = {
    'general': ('general', 'Constancia laboral general'),
    'salary': ('salario', 'Constancia de salario'),
    'seniority': ('antiguedad', 'Constancia de antigüedad'),
}


def _get_or_create_type(cr, code):
    """Obtiene el id del tipo por código, o lo crea si no existe."""
    # Buscar por código exacto primero
    cr.execute("SELECT id FROM hr_work_certificate_type WHERE code = %s LIMIT 1", (code,))
    row = cr.fetchone()
    if row:
        return row[0]
    # Buscar por mapeo (salary->salario, seniority->antiguedad)
    mapped_code, name = CODE_MAP.get(code, (code, 'Constancia %s' % code))
    cr.execute("SELECT id FROM hr_work_certificate_type WHERE code = %s LIMIT 1", (mapped_code,))
    row = cr.fetchone()
    if row:
        return row[0]
    # Crear el tipo (certificate_type_id es required, no podemos dejar NULL)
    cr.execute("""
        INSERT INTO hr_work_certificate_type (name, code, sequence, active, for_portal, create_uid, create_date, write_uid, write_date)
        VALUES (%s, %s, 10, true, true, 1, now(), 1, now())
        RETURNING id;
    """, (name, mapped_code))
    new_id = cr.fetchone()[0]
    _logger.info("Creado hr.work.certificate.type id=%s code=%s para migración", new_id, mapped_code)
    return new_id


def migrate(cr, version):
    if not version:
        return
    # Verificar si existe la tabla del modelo antiguo
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'gn_hr_work_certificate_type'
        );
    """)
    if not cr.fetchone()[0]:
        _logger.info("gn_hr_work_certificate_type no existe, skipping migration")
        return

    # Verificar que existe hr_work_certificate_type (gn_hr_documents)
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'hr_work_certificate_type'
        );
    """)
    if not cr.fetchone()[0]:
        _logger.warning("hr_work_certificate_type no existe, no se puede migrar")
        return

    # Eliminar FK a gn_hr_work_certificate_type para poder apuntar a hr_work_certificate_type
    cr.execute("""
        SELECT constraint_name FROM information_schema.table_constraints
        WHERE table_name = 'gn_hr_work_certificate_request'
        AND constraint_type = 'FOREIGN KEY'
        AND constraint_name LIKE '%certificate_type%';
    """)
    fk_rows = cr.fetchall()
    for (fk_name,) in fk_rows:
        cr.execute(sql.SQL("ALTER TABLE gn_hr_work_certificate_request DROP CONSTRAINT IF EXISTS {}").format(
            sql.Identifier(fk_name)
        ))
        _logger.info("Eliminada FK %s para migración", fk_name)

    # Obtener solicitudes con tipo antiguo
    cr.execute("""
        SELECT r.id, t.code
        FROM gn_hr_work_certificate_request r
        JOIN gn_hr_work_certificate_type t ON t.id = r.certificate_type_id
        WHERE r.certificate_type_id IS NOT NULL;
    """)
    rows = cr.fetchall()

    for request_id, code in rows:
        new_type_id = _get_or_create_type(cr, code)
        cr.execute(
            "UPDATE gn_hr_work_certificate_request SET certificate_type_id = %s WHERE id = %s",
            (new_type_id, request_id),
        )
        cr.execute(
            "UPDATE hr_work_certificate_type SET for_portal = true WHERE id = %s",
            (new_type_id,),
        )
