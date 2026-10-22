# -*- coding: utf-8 -*-
"""Rellenar company_id en hr.document.type tras añadir multicompañía."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'hr_document_type' AND column_name = 'company_id'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        UPDATE hr_document_type
        SET company_id = (SELECT id FROM res_company ORDER BY id LIMIT 1)
        WHERE company_id IS NULL
        """
    )
    _logger.info(
        "post-migrate 19.0.1.0.13: company_id rellenado en hr_document_type donde faltaba."
    )
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'hr_employee_document' AND column_name = 'company_id'
        """
    )
    if cr.fetchone():
        cr.execute(
            """
            UPDATE hr_employee_document d
            SET company_id = e.company_id
            FROM hr_employee e
            WHERE d.employee_id = e.id
              AND (d.company_id IS NULL OR d.company_id IS DISTINCT FROM e.company_id)
            """
        )
        _logger.info(
            "post-migrate 19.0.1.0.13: company_id sincronizado en hr_employee_document."
        )
