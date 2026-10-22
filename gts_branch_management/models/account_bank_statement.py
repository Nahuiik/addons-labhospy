from odoo import api, fields, models


class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'

    @api.model
    def _get_default_branch(self):
        User = self.env['res.users']
        return User.browse(self.env.uid).branch_id.id or False

    branch_id = fields.Many2one('res.branch', 'Branch', default=_get_default_branch)
    gts_no_exigir_sucursal = fields.Boolean(
        string='Sucursal Opcional',
        default=False,
        help='Si está activo, no se exige sucursal en extractos (cuando el campo esté en pantalla).',
    )

    def write(self, vals):
        res = super().write(vals)
        if 'branch_id' in vals:
            self.line_ids._update_move_branch()
        return res
