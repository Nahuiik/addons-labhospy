# -*- coding: utf-8 -*-
from odoo import _, fields, models


class AccountJournal(models.Model):
    _name = "account.journal"
    _inherit = ["account.journal", "gn.audit.mixin"]

    gn_audit_log_count = fields.Integer(
        string="Registros de auditoría",
        compute="_compute_gn_audit_log_count",
    )

    def _compute_gn_audit_log_count(self):
        Log = self.env["gn.audit.log"]
        if not self.ids:
            self.gn_audit_log_count = 0
            return
        groups = Log._read_group(
            domain=[("journal_id", "in", self.ids)],
            groupby=["journal_id"],
            aggregates=["__count"],
        )
        counts = {journal.id: count for journal, count in groups}
        for journal in self:
            journal.gn_audit_log_count = counts.get(journal.id, 0)

    def action_view_gn_audit_logs(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "gn_audit_journal.action_gn_audit_log"
        )
        action["domain"] = [("journal_id", "=", self.id)]
        action["context"] = {"default_journal_id": self.id}
        return action

    # account.journal ya hereda mail.thread y su formulario ya incluye <chatter/>
    # en Odoo 19; solo redeclaramos los campos clave para activar su seguimiento.
    # Al redeclarar con un único atributo, Odoo conserva el resto de la
    # definición original (string, comodel, ayuda, etc.).
    name = fields.Char(tracking=True)
    code = fields.Char(tracking=True)
    type = fields.Selection(tracking=True)
    active = fields.Boolean(tracking=True)
    default_account_id = fields.Many2one(tracking=True)
    suspense_account_id = fields.Many2one(tracking=True)
    currency_id = fields.Many2one(tracking=True)
    bank_account_id = fields.Many2one(tracking=True)
    restrict_mode_hash_table = fields.Boolean(tracking=True)
    refund_sequence = fields.Boolean(tracking=True)
    payment_sequence = fields.Boolean(tracking=True)

    # Campo de gn_banks que controla el uso de múltiples secuencias por diario.
    bank_multi_sequence = fields.Boolean(tracking=True)

    def _gn_audit_journal_fields(self):
        """Campos del diario a registrar en la bitácora (los existentes)."""
        candidates = [
            "name", "code", "type", "active", "default_account_id",
            "suspense_account_id", "currency_id", "bank_account_id",
            "restrict_mode_hash_table", "refund_sequence", "payment_sequence",
            "bank_multi_sequence",
            # Enlaces a secuencias de asientos (journal_sequence / l10n_hn_account).
            "sequence_id", "refund_sequence_id", "debit_sequence_id",
        ]
        return [f for f in candidates if f in self._fields]

    def write(self, vals):
        tracked = self._gn_audit_journal_fields()
        if not any(f in vals for f in tracked):
            return super().write(vals)

        before = {j.id: {f: j[f] for f in tracked} for j in self}
        result = super().write(vals)
        AuditLog = self.env["gn.audit.log"].sudo()
        for journal in self:
            changes = journal._gn_audit_changed_fields(before.get(journal.id, {}), tracked)
            if not changes:
                continue
            # El chatter ya recibe el tracking nativo de los campos con
            # tracking=True; aquí solo alimentamos la bitácora consultable
            # (post_chatter=False evita duplicar la nota).
            AuditLog._gn_create_log(
                journal=journal, operation="journal_config",
                title=_("Configuración del diario modificada"),
                lines=changes, post_chatter=False,
            )
        return result
