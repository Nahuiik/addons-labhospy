# -*- coding: utf-8 -*-
"""Migración layout: nombre único por usuario/compañía."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'purchase_dashboard_layout' AND column_name = 'name'
    """)
    if not cr.fetchone():
        cr.execute("""
            ALTER TABLE purchase_dashboard_layout
            ADD COLUMN IF NOT EXISTS name varchar,
            ADD COLUMN IF NOT EXISTS sequence integer DEFAULT 10,
            ADD COLUMN IF NOT EXISTS is_default boolean DEFAULT false,
            ADD COLUMN IF NOT EXISTS is_shared boolean DEFAULT false,
            ADD COLUMN IF NOT EXISTS share_token varchar,
            ADD COLUMN IF NOT EXISTS shared_from_user_id integer
        """)
        cr.execute("""
            UPDATE purchase_dashboard_layout SET name = 'Principal', is_default = true
            WHERE name IS NULL
        """)
    cr.execute("""
        ALTER TABLE purchase_dashboard_layout
        DROP CONSTRAINT IF EXISTS purchase_dashboard_layout_user_company_uniq
    """)
