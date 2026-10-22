# -*- coding: utf-8 -*-

def migrate(cr, version):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'hr_employee' AND column_name = 'blood_type'
    """)
    if not cr.fetchone():
        return
    cr.execute("""
        ALTER TABLE hr_employee
        ADD COLUMN IF NOT EXISTS x_l10n_hn_blood_type_legacy VARCHAR
    """)
    cr.execute("""
        UPDATE hr_employee
        SET x_l10n_hn_blood_type_legacy = blood_type::text
        WHERE blood_type IS NOT NULL
    """)
