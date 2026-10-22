"""Wizard para auditar y reparar secuencias desalineadas en un solo clic."""
from __future__ import annotations

from odoo import _, api, fields, models


class SequenceAuditWizard(models.TransientModel):
    _name = "gn.sequence.audit.wizard"
    _description = "Auditar y resincronizar secuencias"

    line_ids = fields.One2many(
        "gn.sequence.audit.wizard.line",
        "wizard_id",
        string="Secuencias desalineadas",
    )
    total_desalineadas = fields.Integer(compute="_compute_total", string="Total")

    @api.depends("line_ids")
    def _compute_total(self):
        for w in self:
            w.total_desalineadas = len(w.line_ids)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        Seq = self.env["ir.sequence"].sudo()
        seqs = Seq.search([("prefix", "!=", False)])
        lines = []
        for s in seqs:
            mx = s._gn_get_max_used_number()
            if mx and s.number_next_actual <= mx:
                lines.append((0, 0, {
                    "sequence_id": s.id,
                    "prefix": s.prefix,
                    "number_next_current": s.number_next_actual,
                    "max_usado": mx,
                    "number_next_sugerido": mx + 1,
                    "seleccionar": True,
                }))
        vals["line_ids"] = lines
        return vals

    def action_repair_selected(self):
        seqs = self.line_ids.filtered("seleccionar").mapped("sequence_id")
        if not seqs:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "type": "warning",
                    "title": _("Nada que hacer"),
                    "message": _("No hay secuencias seleccionadas."),
                },
            }
        return seqs.action_gn_resync_from_moves()

    def action_reload(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "target": "new",
            "name": _("Auditar secuencias"),
        }


class SequenceAuditWizardLine(models.TransientModel):
    _name = "gn.sequence.audit.wizard.line"
    _description = "Linea de auditoria de secuencia"
    _order = "max_usado desc, prefix"

    wizard_id = fields.Many2one("gn.sequence.audit.wizard", required=True, ondelete="cascade")
    sequence_id = fields.Many2one("ir.sequence", required=True, string="Secuencia")
    prefix = fields.Char(string="Prefijo")
    number_next_current = fields.Integer(string="Siguiente actual")
    max_usado = fields.Integer(string="Max usado")
    number_next_sugerido = fields.Integer(string="Siguiente sugerido")
    seleccionar = fields.Boolean(string="Reparar", default=True)
