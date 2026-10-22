# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    closing_line_sequence = fields.Integer(
        string="#",
        compute="_compute_closing_line_sequence",
        store=True,
        help="Número de secuencia en listas del Cierre de Caja",
    )

    @api.depends()
    def _compute_closing_line_sequence(self):
        """Número de fila (1, 2, 3...) cuando se muestra en listas del Cierre de Caja."""
        for rec in self:
            rec.closing_line_sequence = 0

        # Buscar el cierre que contiene estos moves (no depender del context active_id)
        closing = self.env["gn.cash.closing"].search([
            "|", "|",
            ("invoice_open_ids", "in", self.ids),
            ("invoice_paid_ids", "in", self.ids),
            ("invoice_cancelled_ids", "in", self.ids),
        ], limit=1)
        if not closing:
            return

        seq_by_id = {}
        for field_name in ("invoice_open_ids", "invoice_paid_ids", "invoice_cancelled_ids"):
            for i, move in enumerate(getattr(closing, field_name), start=1):
                seq_by_id[move.id] = i

        for rec in self:
            rec.closing_line_sequence = seq_by_id.get(rec.id, 0)
