# -*- coding: utf-8 -*-
"""Al cambiar el diario en borrador: nuevo correlativo IR de banco y sincronización con account.move enlazado."""
from odoo import models, _
from odoo.exceptions import UserError


class GnBankDocumentJournalMixin(models.AbstractModel):
    _name = 'gn.banks.document.journal.mixin'
    _description = 'Renumeración de documento bancario al cambiar diario en borrador'

    def write(self, vals):
        jid = vals.get('journal_id')
        if jid and not self.env.context.get('skip_gn_banks_journal_resequence'):
            self._gn_banks_resequence_on_journal_change(jid)
        res = super().write(vals)
        if jid:
            self._gn_banks_sync_linked_move_after_journal_change()
        return res

    def _gn_banks_ir_sequence_move_type(self):
        """Valor de ``ir.sequence.move_type``: provisiones usan método _sequence_move_type."""
        self.ensure_one()
        getter = getattr(self, '_sequence_move_type', None)
        if callable(getter):
            return getter()
        mt = getattr(self, 'move_type', None)
        return mt if mt else False

    def _gn_banks_resequence_on_journal_change(self, new_journal_id):
        for rec in self:
            if getattr(rec, 'state', None) != 'draft':
                continue
            if not rec.journal_id or rec.journal_id.id == new_journal_id:
                continue
            mt = rec._gn_banks_ir_sequence_move_type()
            if not mt:
                continue
            journal = rec.env['account.journal'].browse(new_journal_id)
            # SUDO-JUSTIFIED: secuencias ir.sequence por diario pueden requerir acceso elevado
            seq = rec.env['ir.sequence'].sudo().search(
                [('move_type', '=', mt), ('journal_id', '=', new_journal_id)],
                limit=1,
            )
            if not seq:
                Provision = rec.env['bank.provision']
                if mt == 'provision':
                    default_journal = Provision._get_company_accrual_provision_journal(rec.company_id)
                elif mt == 'fx_differential':
                    default_journal = Provision._get_company_fx_differential_journal(rec.company_id)
                else:
                    default_journal = False
                if default_journal and default_journal.id == new_journal_id:
                    seq = rec.env['bank.provision.sequence.helper'].ensure_journal_sequence(journal, mt)
            if not seq:
                raise UserError(
                    _(
                        "No hay secuencia para el diario «%s» y el tipo de movimiento «%s». "
                        "Configure una secuencia en el diario antes de cambiar.",
                    )
                    % (
                        rec.env['account.journal'].browse(new_journal_id).display_name,
                        mt,
                    ),
                )
            rec.name = seq.next_by_id()

    def _gn_banks_sync_linked_move_after_journal_change(self):
        for rec in self:
            move = getattr(rec, 'move_id', None)
            if not move:
                continue
            if move.state != 'draft':
                continue
            if move.journal_id == rec.journal_id:
                continue
            move.write({'name': '/', 'journal_id': rec.journal_id.id})
            if rec.name not in ('/', '', False):
                move.write({'name': rec.name})
