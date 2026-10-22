# -*- coding: utf-8 -*-
"""Marca tipos recepción existentes para Productos entrantes."""


def migrate(cr, version):
    cr.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'stock_picking_type'
          AND column_name = 'use_in_consume_product'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        UPDATE stock_picking_type
           SET use_in_consume_product = TRUE
         WHERE code = 'incoming'
           AND COALESCE(use_in_consume_product, FALSE) = FALSE
        """
    )
