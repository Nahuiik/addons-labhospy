# -*- coding: utf-8 -*-
"""Rellenar company_id en auditoría portal."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'gn_hr_portal_audit_log' AND column_name = 'company_id'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        UPDATE gn_hr_portal_audit_log l
        SET company_id = e.company_id
        FROM hr_employee e
        WHERE l.employee_id = e.id
          AND e.company_id IS NOT NULL
          AND l.company_id IS NULL
        """
    )
    cr.execute(
        """
        UPDATE gn_hr_portal_audit_log l
        SET company_id = u.company_id
        FROM res_users u
        WHERE l.user_id = u.id
          AND u.company_id IS NOT NULL
          AND l.company_id IS NULL
        """
    )
    cr.execute(
        """
        UPDATE gn_hr_portal_audit_log
        SET company_id = (SELECT id FROM res_company ORDER BY id LIMIT 1)
        WHERE company_id IS NULL
        """
    )
    _logger.info("post-migrate 19.0.1.0.28: company_id rellenado en gn_hr_portal_audit_log.")
