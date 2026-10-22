from odoo import models, fields, api, _


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    is_writeoff_line = fields.Boolean(string='Is Writeoff Line', default=False, copy=False)