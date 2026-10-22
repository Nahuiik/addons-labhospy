"""Utilidades para resincronizar ir.sequence contra los asientos ya existentes.

Corrige el error 'Ya existe otro asiento con el mismo nombre' que aparece
cuando la secuencia (ir.sequence) queda desalineada con account.move.name
tras importaciones masivas o creaciones con nombre manual.

La resincronizacion es no destructiva:
- No renumera asientos existentes.
- No cambia el prefix ni el padding.
- Solo ajusta number_next_actual al maximo detectado + 1.
"""
from __future__ import annotations

import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class IrSequence(models.Model):
    _inherit = "ir.sequence"

    gn_max_used_number = fields.Integer(
        string="Numero maximo usado",
        compute="_compute_gn_max_used_number",
        help="Mayor sufijo numerico encontrado en account.move.name que coincida con el prefijo de esta secuencia.",
    )
    gn_needs_resync = fields.Boolean(
        string="Requiere resincronizacion",
        compute="_compute_gn_max_used_number",
        help="Verdadero si la secuencia generaria un numero ya existente.",
    )

    @api.depends("prefix", "padding", "number_next_actual")
    def _compute_gn_max_used_number(self):
        for seq in self:
            mx = seq._gn_get_max_used_number()
            seq.gn_max_used_number = mx
            seq.gn_needs_resync = bool(mx) and seq.number_next_actual <= mx

    def _gn_get_max_used_number(self) -> int:
        """Devuelve el mayor sufijo numerico usado en account.move para este prefix.

        Devuelve 0 si:
        - No hay prefix.
        - El prefix contiene placeholders (%(year)s, %(range_year)s, ...).
        - No hay asientos que coincidan.
        """
        self.ensure_one()
        prefix = self.prefix or ""
        if not prefix or "%(" in prefix:
            return 0
        Move = self.env["account.move"].sudo()
        moves = Move.search([("name", "=like", prefix + "%")])
        max_num = 0
        for m in moves:
            tail = (m.name or "")[len(prefix):]
            m2 = re.match(r"^(\d+)$", tail)
            if not m2:
                continue
            n = int(m2.group(1))
            if n > max_num:
                max_num = n
        return max_num

    def action_gn_resync_from_moves(self):
        """Ajusta number_next_actual al maximo detectado + 1 (y sus date_ranges)."""
        fixed = []
        for seq in self:
            mx = seq._gn_get_max_used_number()
            if not mx:
                continue
            new_next = mx + 1
            old_next = seq.number_next_actual
            if new_next <= old_next:
                continue
            seq.number_next_actual = new_next
            for dr in seq.date_range_ids:
                if dr.number_next_actual < new_next:
                    dr.number_next_actual = new_next
            fixed.append((seq.prefix or seq.code, old_next, new_next, mx))
            _logger.info(
                "gn_sequence_resync: %s number_next %s -> %s (max_usado=%s)",
                seq.prefix or seq.code, old_next, new_next, mx,
            )
        if not fixed:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "type": "success",
                    "title": _("Sin cambios"),
                    "message": _("Todas las secuencias seleccionadas ya estan alineadas."),
                    "sticky": False,
                },
            }
        detalle = "\n".join(
            _("%s: %s -> %s (max usado: %s)") % (p, o, n, m) for p, o, n, m in fixed
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "title": _("Secuencias resincronizadas (%s)") % len(fixed),
                "message": detalle,
                "sticky": True,
            },
        }

    @api.model
    def _gn_cron_audit_sequences(self):
        """Cron opcional: registra en el log las secuencias desalineadas."""
        seqs = self.sudo().search([("prefix", "!=", False)])
        report = []
        for s in seqs:
            mx = s._gn_get_max_used_number()
            if mx and s.number_next_actual <= mx:
                report.append((s.id, s.prefix, s.number_next_actual, mx))
        if not report:
            _logger.info("gn_sequence_resync cron: 0 secuencias desalineadas.")
            return
        _logger.warning(
            "gn_sequence_resync cron: %s secuencias necesitan resync:\n%s",
            len(report),
            "\n".join(
                f"  seq_id={sid} prefix={pref!r} next={nx} max_usado={mx}"
                for sid, pref, nx, mx in report
            ),
        )
