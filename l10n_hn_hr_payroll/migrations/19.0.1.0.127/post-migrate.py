# -*- coding: utf-8 -*-
"""Rellenar company_id en res.bank tras multicompañía."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'res_bank' AND column_name = 'company_id'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        UPDATE res_bank
        SET company_id = (SELECT id FROM res_company ORDER BY id LIMIT 1)
        WHERE company_id IS NULL
        """
    )
    _logger.info("post-migrate 19.0.1.0.127: company_id rellenado en res_bank donde faltaba.")
