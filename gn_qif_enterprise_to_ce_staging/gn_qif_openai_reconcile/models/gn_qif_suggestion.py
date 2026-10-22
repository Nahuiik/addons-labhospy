# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class GnQifSuggestion(models.Model):
    _name = 'gn.qif.suggestion'
    _description = 'Sugerencia de análisis QIF (IA)'
    _order = 'create_date desc'
    _inherit = ['mail.thread']
    _check_company_auto = True

    name = fields.Char(string='Título', compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    journal_id = fields.Many2one(
        'account.journal', string='Diario',
        domain="[('type', 'in', ('bank', 'cash'))]",
        index=True,
    )
    summary = fields.Text(string='Resumen')
    detail = fields.Text(string='Detalle (JSON)')
    state = fields.Selection([
        ('new', 'Nuevo'),
        ('seen', 'Visto'),
        ('applied', 'Aplicado'),
        ('dismissed', 'Descartado'),
    ], default='new', string='Estado', tracking=True)
    qif_filename = fields.Char(string='Archivo QIF')

    @api.depends('journal_id', 'create_date', 'summary', 'qif_filename')
    def _compute_name(self):
        for rec in self:
            j = rec.journal_id.name if rec.journal_id else _('Sin diario')
            rec.name = f'{rec.qif_filename or "QIF"} — {j}'

    def action_set_seen(self):
        self.write({'state': 'seen'})

    def action_set_applied(self):
        self.write({'state': 'applied'})

    def action_set_dismissed(self):
        self.write({'state': 'dismissed'})
