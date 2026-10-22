# -*- coding: utf-8 -*-
"""Actualiza secuencias aunque ir.model.data tenga noupdate (instalaciones antiguas)."""


def cleanup_l10n_duplicate_consume_sequences(env):
    """Quita secuencias duplicadas (mismo código) creadas por l10n_hn_stock/data obsoleto."""
    md = env["ir.model.data"].sudo().search(
        [
            ("module", "=", "l10n_hn_stock"),
            ("model", "=", "ir.sequence"),
            ("name", "in", ("consume_product_sequence", "incoming_product_sequence")),
        ]
    )
    for row in md:
        seq = env["ir.sequence"].sudo().browse(row.res_id)
        row.unlink()
        if seq.exists():
            seq.unlink()


def sync_consume_sequences(env):
    cleanup_l10n_duplicate_consume_sequences(env)
    consume = env.ref(
        "gn_consume_product.consume_product_sequence", raise_if_not_found=False
    )
    if consume:
        consume.write(
            {
                "prefix": "PC-%(y)s-%(month)s-%(day)s-",
                "padding": 5,
                "use_date_range": True,
            }
        )
    incoming = env.ref(
        "gn_consume_product.incoming_product_sequence", raise_if_not_found=False
    )
    if incoming:
        incoming.write(
            {
                "prefix": "PE-%(y)s-%(month)s-%(day)s-",
                "padding": 5,
                "use_date_range": True,
            }
        )
    meta = env["ir.model.data"].search(
        [
            ("module", "=", "gn_consume_product"),
            (
                "name",
                "in",
                ("consume_product_sequence", "incoming_product_sequence"),
            ),
        ]
    )
    meta.write({"noupdate": False})


def post_init_hook(env):
    sync_consume_sequences(env)
