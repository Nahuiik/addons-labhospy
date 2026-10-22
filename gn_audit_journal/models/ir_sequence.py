# -*- coding: utf-8 -*-
from odoo import _, api, models

# Campos de enlace en account.journal que apuntan a una ir.sequence usada para
# numerar asientos contables (factura/NC/ND). Existen si journal_sequence o
# l10n_hn_account están instalados.
_JOURNAL_SEQUENCE_LINKS = ("sequence_id", "refund_sequence_id", "debit_sequence_id")


class IrSequence(models.Model):
    _name = "ir.sequence"
    _inherit = ["ir.sequence", "gn.audit.mixin"]

    def _gn_audit_tracked_fields(self):
        candidates = [
            "name", "code", "move_type", "prefix", "suffix", "padding",
            "number_next_actual", "number_increment", "implementation",
            "use_date_range", "active", "journal_id", "company_id",
            # Campos fiscales (CAI/SAR) de l10n_hn_account, si están presentes.
            "start_date", "percentage_alert",
        ]
        return [f for f in candidates if f in self._fields]

    def _gn_audit_journals(self):
        """Diarios relacionados: bancarios (journal_id) y contables (enlaces)."""
        self.ensure_one()
        Journal = self.env["account.journal"]
        journals = Journal
        if "journal_id" in self._fields and self.journal_id:
            journals |= self.journal_id
        link_fields = [f for f in _JOURNAL_SEQUENCE_LINKS if f in Journal._fields]
        if link_fields:
            domain = ["|"] * (len(link_fields) - 1) + [
                (f, "=", self.id) for f in link_fields
            ]
            journals |= Journal.sudo().search(domain)
        return journals

    def _gn_seq_label(self):
        self.ensure_one()
        return self.name or self.code or str(self.id)

    def _gn_seq_move_type(self):
        self.ensure_one()
        return self.move_type if "move_type" in self._fields else False

    # -- create / write / unlink ----------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        AuditLog = self.env["gn.audit.log"].sudo()
        for seq in records:
            journals = seq._gn_audit_journals()
            if not journals:
                continue
            lines = [
                seq._gn_audit_value_line(f, seq[f])
                for f in ("move_type", "prefix", "padding",
                          "number_next_actual", "implementation")
                if f in seq._fields
            ]
            title = _("Secuencia creada: %s") % seq._gn_seq_label()
            for journal in journals:
                AuditLog._gn_create_log(
                    journal=journal, operation="seq_create", title=title,
                    lines=lines, sequence_id=seq.id,
                    sequence_name=seq._gn_seq_label(),
                    move_type=seq._gn_seq_move_type(),
                )
        return records

    def write(self, vals):
        tracked = self._gn_audit_tracked_fields()
        if not any(f in vals for f in tracked):
            return super().write(vals)

        before = {seq.id: {f: seq[f] for f in tracked} for seq in self}
        before_journals = {seq.id: seq._gn_audit_journals() for seq in self}
        result = super().write(vals)
        AuditLog = self.env["gn.audit.log"].sudo()
        for seq in self:
            changes = seq._gn_audit_changed_fields(before.get(seq.id, {}), tracked)
            if not changes:
                continue
            title = _("Secuencia modificada: %s") % seq._gn_seq_label()
            # Unión de diarios antes y después (cubre reasignaciones de diario).
            journals = before_journals.get(seq.id, self.env["account.journal"])
            journals |= seq._gn_audit_journals()
            for journal in journals:
                AuditLog._gn_create_log(
                    journal=journal, operation="seq_write", title=title,
                    lines=changes, sequence_id=seq.id,
                    sequence_name=seq._gn_seq_label(),
                    move_type=seq._gn_seq_move_type(),
                )
        return result

    def unlink(self):
        AuditLog = self.env["gn.audit.log"].sudo()
        audits = []
        for seq in self:
            journals = seq._gn_audit_journals()
            if not journals:
                continue
            lines = []
            if "move_type" in seq._fields:
                lines.append(seq._gn_audit_value_line("move_type", seq.move_type))
            audits.append((
                journals,
                _("Secuencia eliminada: %s") % seq._gn_seq_label(),
                lines,
                seq._gn_seq_label(),
                seq._gn_seq_move_type(),
            ))
        result = super().unlink()
        for journals, title, lines, name, move_type in audits:
            for journal in journals:
                AuditLog._gn_create_log(
                    journal=journal, operation="seq_unlink", title=title,
                    lines=lines, sequence_id=False,
                    sequence_name=name, move_type=move_type,
                )
        return result
