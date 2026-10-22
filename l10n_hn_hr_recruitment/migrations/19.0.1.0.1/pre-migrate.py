# -*- coding: utf-8 -*-
"""Rename hr.employee column after field hn_country_id replaces countryemployee_bank_id_id."""


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'hr_employee'
          AND column_name = 'countryemployee_bank_id_id'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'hr_employee' AND column_name = 'hn_country_id'
        """
    )
    if cr.fetchone():
        return
    cr.execute(
        'ALTER TABLE hr_employee RENAME COLUMN countryemployee_bank_id_id TO hn_country_id'
    )
