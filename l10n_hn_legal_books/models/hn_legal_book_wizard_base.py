# -*- coding: utf-8 -*-
from odoo import fields, models

DISPLAY_TYPE_EXCLUDE = ('line_section', 'line_note', 'line_subsection')


class HnLegalBookWizardBase(models.AbstractModel):
    _name = 'hn.legal.book.wizard.base'
    _description = 'Base libros legales HN'

    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(required=True, default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(required=True, default=fields.Date.today)
    journal_ids = fields.Many2many(
        'account.journal',
        string='Diarios',
        domain="[('company_id', '=', company_id)]",
        check_company=True,
        help='Vacío = todos los diarios de la compañía.',
    )
    target_move = fields.Selection(
        [
            ('posted', 'Solo asientos publicados'),
            ('all', 'Borrador y publicados'),
        ],
        default='posted',
        required=True,
    )

    def _parent_state_domain(self):
        self.ensure_one()
        if self.target_move == 'posted':
            return [('parent_state', '=', 'posted')]
        return [('parent_state', 'in', ('draft', 'posted'))]

    def _journal_domain(self):
        self.ensure_one()
        if self.journal_ids:
            return [('journal_id', 'in', self.journal_ids.ids)]
        return []

    def _aml_base_domain(self, extra=None):
        self.ensure_one()
        domain = [
            *self._parent_state_domain(),
            ('company_id', 'child_of', self.company_id.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('display_type', 'not in', DISPLAY_TYPE_EXCLUDE),
        ]
        domain += self._journal_domain()
        if extra:
            domain.extend(extra)
        return domain
