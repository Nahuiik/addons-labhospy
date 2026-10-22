# -*- coding: utf-8 -*-
# See README.md: independent CE implementation; do not copy OEEL/OCA sources.

from odoo import fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    hn_posted_uid = fields.Many2one(
        comodel_name="res.users",
        string="Posted by (HN)",
        readonly=True,
        copy=False,
        help="Last user recorded when this move was posted via l10n_hn_base.",
    )
    hn_posted_at = fields.Datetime(
        string="Posted at (HN)",
        readonly=True,
        copy=False,
        help="Timestamp when posting was last recorded by l10n_hn_base.",
    )

    def _post(self, soft=True):
        res = super()._post(soft=soft)
        posted = self.filtered(lambda m: m.state == "posted")
        if posted:
            posted.write(
                {
                    "hn_posted_uid": self.env.uid,
                    "hn_posted_at": fields.Datetime.now(),
                }
            )
        return res


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def action_hn_open_statement_line(self):
        """Open the related bank statement line from a journal item, if any."""
        self.ensure_one()
        if not self.statement_line_id:
            raise UserError(_("This journal item is not linked to a bank statement line."))
        return self.statement_line_id.action_hn_open_reconciliation()

    def action_hn_open_move(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.move_id.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
        }
