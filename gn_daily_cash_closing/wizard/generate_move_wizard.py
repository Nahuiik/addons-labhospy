# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo import Command


class GnCashClosingGenerateMoveWizard(models.TransientModel):
    _name = "gn.cash.closing.generate.move.wizard"
    _description = "Wizard Generar Asiento de Cierre de Caja"

    closing_id = fields.Many2one(
        "gn.cash.closing",
        string="Cierre de Caja",
        required=True,
        ondelete="cascade",
    )
    cash_journal_id = fields.Many2one(
        "account.journal",
        string="Diario de Efectivo",
        readonly=True,
    )
    deposit_move_ids = fields.Many2many(
        "account.move",
        string="Depósitos del día",
        readonly=True,
    )
    bank_journal_id = fields.Many2one(
        "account.journal",
        string="Banco de Depósito",
        required=True,
    )
    amount_efectivo = fields.Float(string="Monto Efectivo", readonly=True)
    amount_anticipos = fields.Float(string="Monto Anticipos/Abonos", readonly=True)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get("active_id")
        if not active_id:
            return res
        closing = self.env["gn.cash.closing"].browse(active_id)
        if not closing.exists():
            return res
        report = self.env["report.gn_daily_cash_closing.cash_closing_template"]
        branch_id = closing.branch_id.id
        report_date = closing.date
        domain = [
            ("payment_type", "=", "inbound"),
            ("state", "in", ["in_process", "paid"]),
            ("date", "=", report_date),
            ("branch_id", "=", branch_id),
        ]
        payments = self.env["account.payment"].search(domain)
        efectivo = anticipos = 0.0
        cash_journals = {}
        deposit_moves = self.env["account.move"]
        for pay in payments:
            mode = report._get_payment_mode(pay.journal_id)
            amount = pay.amount or 0.0
            is_advance = getattr(pay, "is_advance", False)
            if is_advance:
                anticipos += amount
            elif mode == "efectivo":
                efectivo += amount
            else:
                continue
            if pay.journal_id and (pay.journal_id.type == "cash" or mode == "efectivo"):
                jid = pay.journal_id.id
                cash_journals[jid] = cash_journals.get(jid, 0) + amount
            if pay.move_id and pay.move_id.state == "posted":
                deposit_moves |= pay.move_id
        cash_journal_id = False
        if cash_journals:
            cash_journal_id = max(cash_journals, key=cash_journals.get)
            cash_journal_id = self.env["account.journal"].browse(cash_journal_id)
        if cash_journal_id:
            deposit_moves = deposit_moves.filtered(
                lambda m: m.journal_id.id == cash_journal_id.id
            )
        res["closing_id"] = closing.id
        res["cash_journal_id"] = cash_journal_id.id if cash_journal_id else False
        res["deposit_move_ids"] = [Command.set(deposit_moves.ids)]
        res["amount_efectivo"] = efectivo
        res["amount_anticipos"] = anticipos
        res["company_id"] = (
            closing.branch_id.company_id.id if closing.branch_id else self.env.company.id
        )
        return res

    def action_create_move(self):
        self.ensure_one()
        if self.amount_efectivo + self.amount_anticipos <= 0:
            raise UserError(
                _("No hay monto de efectivo ni anticipos para generar el asiento.")
            )
        if not self.cash_journal_id:
            raise UserError(
                _("No se pudo identificar el diario de efectivo. Verifique que existan pagos en efectivo o anticipos del día.")
            )
        if not self.bank_journal_id:
            raise ValidationError(_("Debe seleccionar el banco de depósito."))
        cash_account = self.cash_journal_id.default_account_id
        bank_account = self.bank_journal_id.default_account_id
        if not cash_account:
            raise UserError(
                _("El diario de efectivo '%s' no tiene cuenta por defecto configurada.")
                % self.cash_journal_id.name
            )
        if not bank_account:
            raise UserError(
                _("El diario de banco '%s' no tiene cuenta por defecto configurada.")
                % self.bank_journal_id.name
            )
        total = self.amount_efectivo + self.amount_anticipos
        line_vals = [
            (0, 0, {
                "name": _("Cierre de caja %s") % self.closing_id.name,
                "account_id": bank_account.id,
                "debit": total,
                "credit": 0.0,
            }),
        ]
        if self.amount_efectivo:
            line_vals.append((0, 0, {
                "name": _("Cierre de caja efectivo"),
                "account_id": cash_account.id,
                "debit": 0.0,
                "credit": self.amount_efectivo,
            }))
        if self.amount_anticipos:
            line_vals.append((0, 0, {
                "name": _("Cierre de caja abonos"),
                "account_id": cash_account.id,
                "debit": 0.0,
                "credit": self.amount_anticipos,
            }))
        move_vals = {
            "move_type": "entry",
            "journal_id": self.bank_journal_id.id,
            "date": self.closing_id.date,
            "ref": _("Cierre de caja %s") % self.closing_id.name,
            "line_ids": line_vals,
        }
        if "branch_id" in self.env["account.move"]._fields and self.closing_id.branch_id:
            move_vals["branch_id"] = self.closing_id.branch_id.id
        move = self.env["account.move"].create(move_vals)
        move.action_post()
        self.closing_id.write({"move_id": move.id})
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": move.id,
            "view_mode": "form",
            "target": "current",
        }
