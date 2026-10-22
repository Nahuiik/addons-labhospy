# -*- coding: utf-8 -*-
"""Alinea NOT NULL en sale_order.picking_policy (sale_stock) para silenciar odoo.schema."""


def migrate(cr, version):
    # SQL-JUSTIFIED: migración Odoo — alinear NOT NULL en sale_order.picking_policy (sin entrada de usuario).
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sale_order' AND column_name = 'picking_policy'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        UPDATE sale_order SET picking_policy = 'direct'
        WHERE picking_policy IS NULL
        """
    )
    cr.execute(
        """
        ALTER TABLE sale_order ALTER COLUMN picking_policy SET NOT NULL
        """
    )
