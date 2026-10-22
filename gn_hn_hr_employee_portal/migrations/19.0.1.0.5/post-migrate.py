# -*- coding: utf-8 -*-
"""
Asigna secuencia a solicitudes existentes que no tienen name.
"""
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'gn_hr_work_certificate_request'
        AND column_name = 'name';
    """)
    if not cr.fetchone():
        return
    cr.execute("""
        SELECT id FROM gn_hr_work_certificate_request
        WHERE name IS NULL OR name = ''
        ORDER BY id;
    """)
    rows = cr.fetchall()
    if not rows:
        return
    year = datetime.now().year
    for i, (rid,) in enumerate(rows, start=1):
        name = "SOL-%s-%05d" % (year, i)
        cr.execute(
            "UPDATE gn_hr_work_certificate_request SET name = %s WHERE id = %s",
            (name, rid),
        )
