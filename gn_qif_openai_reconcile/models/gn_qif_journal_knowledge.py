# -*- coding: utf-8 -*-
from odoo import fields, models


class GnQifJournalKnowledge(models.Model):
    _name = 'gn.qif.journal.knowledge'
    _description = 'Conocimiento QIF por diario'
    _inherit = ['mail.thread']
    _check_company_auto = True

    journal_id = fields.Many2one(
        'account.journal', string='Diario', required=True, ondelete='cascade',
        domain="[('type', 'in', ('bank', 'cash'))]",
        index=True,
    )
    company_id = fields.Many2one(
        related='journal_id.company_id', store=True, readonly=True,
    )
    bank_id = fields.Many2one(
        related='journal_id.bank_id', string='Banco', readonly=True,
    )
    user_notes = fields.Html(
        string='Instrucciones y hallazgos',
        help='Políticas del equipo para este banco/diario. Se envían a la IA en cada análisis.',
    )

    _journal_knowledge_unique = models.Constraint(
        'unique (journal_id)',
        'Ya existe un registro de conocimiento para este diario.',
    )
