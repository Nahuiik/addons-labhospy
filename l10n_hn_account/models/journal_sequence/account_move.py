from odoo import api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    sequence_generated = fields.Boolean(string="Sequence Generated", copy=False)

    @api.depends('posted_before', 'state', 'journal_id', 'date')
    def _compute_name(self):
        draft_states = (False, 'draft')
        # En onchange web el registro puede tener _origin pero id NewId (aún no guardado).
        unsaved_moves = self.filtered(lambda m: not isinstance(m.id, int))
        saved_moves = self - unsaved_moves

        for move in unsaved_moves:
            if move.journal_id.sequence_id and move.state in draft_states:
                move.name = '/'

        if not saved_moves:
            return

        without_sequence = saved_moves.filtered(lambda m: not m.journal_id.sequence_id)
        with_sequence = saved_moves - without_sequence

        if without_sequence:
            super(AccountMove, without_sequence)._compute_name()

        for move in with_sequence:
            sequence_id = move._get_sequence()
            if not sequence_id:
                raise UserError('Please define a sequence on your journal.')
            if not move.sequence_generated and move.state in draft_states:
                move.name = '/'
            elif not move.sequence_generated and move.state not in draft_states:
                invoice_date = move.invoice_date or fields.Date.today()
                move.name = sequence_id.with_context(
                    ir_sequence_date=invoice_date,
                    bypass_constrains=True,
                ).next_by_id(sequence_date=invoice_date)
                move.sequence_generated = True

    def _get_sequence(self):
        """Return the sequence to be used during the post of the current move."""
        self.ensure_one()

        journal = self.journal_id

        # Detectar si es una nota de débito (tiene debit_origin_id)
        is_debit_note = hasattr(self, 'debit_origin_id') and self.debit_origin_id

        # Si es nota de débito y tiene secuencia configurada, usar debit_sequence_id
        if is_debit_note and journal.debit_sequence_id:
            return journal.debit_sequence_id

        # Si es nota de crédito (refund) y tiene secuencia configurada, usar refund_sequence_id
        if self.move_type in ('out_refund', 'in_refund') and journal.refund_sequence and journal.refund_sequence_id:
            return journal.refund_sequence_id

        # Para facturas normales, entradas y recibos, usar sequence_id
        if self.move_type in ('entry', 'out_invoice', 'in_invoice', 'out_receipt', 'in_receipt') or not journal.refund_sequence:
            return journal.sequence_id

        # Fallback a refund_sequence_id si está configurado
        if journal.refund_sequence_id:
            return journal.refund_sequence_id

        return journal.sequence_id

    @api.model
    def _get_invoice_in_payment_state(self):
        # OVERRIDE to enable the 'in_payment' state on invoices.
        return 'paid'
