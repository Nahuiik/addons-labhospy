from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    sequence_generated = fields.Boolean(string="Sequence Generated", copy=False)

    def _gn_banks_has_linked_bank_document_move(self):
        """Hay un documento gn_banks que enlaza este asiento por move_id (no exige sequence_generated)."""
        self.ensure_one()
        if self.move_type != 'entry':
            return False
        bid = self.id
        if not bid:
            return False
        for model_name in ('bank.check', 'bank.transfer', 'debit.credit', 'bank.provision'):
            if model_name not in self.env.registry:
                continue
            if self.env[model_name].sudo().search([('move_id', '=', bid)], limit=1):
                return True
        return False

    def _gn_banks_journal_change_must_reset_name_first(self, new_journal_id):
        """Aplica mismo bypass que Odoo (name '/') al cambiar diario; enlazados gn_banks.

        Incluye borradores cuyo asiento viene de revertir desde publicado
        (``posted_before`` True), típico de cancelar cheque y «volver a borrador».
        """
        self.ensure_one()
        return (
            not self.quick_edit_mode
            and self.state == 'draft'
            and self.move_type == 'entry'
            and bool(self.journal_id)
            and self.journal_id.id != new_journal_id
            and self.name not in ('/', '', False)
            and self._gn_banks_has_linked_bank_document_move()
        )

    def write(self, vals):
        if not vals:
            return True
        vals = dict(vals)

        jid = vals.get('journal_id')
        if jid and 'name' not in vals:
            new_jid = jid
            need_slash_with_journal = self.filtered(
                lambda m: m._gn_banks_journal_change_must_reset_name_first(new_jid),
            )
            if need_slash_with_journal:
                rest = self - need_slash_with_journal
                merged = dict(vals)
                merged['name'] = '/'
                # Un solo write por registro cumple ambas validaciones estándar.
                super(AccountMove, need_slash_with_journal).write(merged)
                if rest:
                    return super(AccountMove, rest).write(vals)
                return True

        return super().write(vals)

    def _get_valid_journal_types(self):
        """Permitir diarios banco/caja en asientos 'entry' generados por gn_banks.

        El estándar solo admite 'general' para move_type entry; si no, _compute_journal_id
        sustituye el diario banco y más adelante aparece el error al intentar cambiar
        journal_id con nombre/número de secuencia ya asignado.
        """
        types = super()._get_valid_journal_types()
        if self.move_type == 'entry' and self.sequence_generated:
            merged = list(types)
            for jtype in ('bank', 'cash'):
                if jtype not in merged:
                    merged.append(jtype)
            return merged
        return types
