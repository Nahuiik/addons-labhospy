# -*- coding: utf-8 -*-
"""Pre-migrate: add country_id to hr.license.type and set HN for existing records."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Check if hr_license_type table exists (module might not be installed)
    cr.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = current_schema()
            AND table_name = 'hr_license_type'
        )
    """)
    if not cr.fetchone()[0]:
        return

    # Get Honduras country id
    cr.execute("SELECT id FROM res_country WHERE code = 'HN' LIMIT 1")
    row = cr.fetchone()
    if not row:
        _logger.warning("Country HN not found, skipping hr.license.type migration")
        return

    country_hn_id = row[0]

    # Add column if not exists (for pre-38 installations)
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = current_schema()
        AND table_name = 'hr_license_type'
        AND column_name = 'country_id'
    """)
    if not cr.fetchone():
        # Drop old unique(name) constraint if exists (PostgreSQL auto-names it)
        cr.execute("""
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'hr_license_type'::regclass
            AND contype = 'u'
            AND pg_get_constraintdef(oid) LIKE 'UNIQUE (name)%'
        """)
        for (conname,) in cr.fetchall():
            cr.execute(
                'ALTER TABLE hr_license_type DROP CONSTRAINT IF EXISTS "{}"'.format(
                    conname.replace('"', '""')
                ),
            )

        cr.execute(
            "ALTER TABLE hr_license_type ADD COLUMN country_id INTEGER",
        )
        cr.execute(
            "UPDATE hr_license_type SET country_id = %s WHERE country_id IS NULL",
            (country_hn_id,),
        )
        cr.execute(
            "ALTER TABLE hr_license_type ALTER COLUMN country_id SET NOT NULL",
        )
        _logger.info(
            "Migrated hr.license.type: added country_id and set HN for existing records"
        )
