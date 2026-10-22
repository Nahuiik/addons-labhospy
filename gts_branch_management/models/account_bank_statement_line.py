from odoo import api, fields, models


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    branch_id = fields.Many2one(
        'res.branch',
        string='Branch',
        related='statement_id.branch_id',
        store=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        statement_lines = super().create(vals_list)
        statement_lines._update_move_branch()
        return statement_lines

    def write(self, vals):
        res = super().write(vals)
        if any(field in vals for field in {'branch_id', 'statement_id'}):
            self._update_move_branch()
        return res

    def _prepare_move_line_default_vals(self, counterpart_account_id=None):
        line_vals_list = super()._prepare_move_line_default_vals(counterpart_account_id=counterpart_account_id)
        branch_id = self.branch_id.id
        if branch_id:
            for vals in line_vals_list:
                vals.setdefault('branch_id', branch_id)
        return line_vals_list

    def _update_move_branch(self):
        for st_line in self.filtered(lambda l: l.move_id):
            branch_id = st_line.branch_id.id
            if not branch_id:
                continue
            st_line.move_id.with_context(
                skip_account_move_synchronization=True,
                skip_readonly_check=True,
            ).write({'branch_id': branch_id})
            st_line.move_id.line_ids.with_context(check_move_validity=False).write({'branch_id': branch_id})
