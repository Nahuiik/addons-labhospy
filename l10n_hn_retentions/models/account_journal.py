from odoo import models, fields, api


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    is_retention = fields.Boolean(string='')
    retention_seq = fields.Many2one('ir.sequence', string="Retention")