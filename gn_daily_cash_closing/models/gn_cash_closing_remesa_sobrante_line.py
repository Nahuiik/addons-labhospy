# -*- coding: utf-8 -*-
from odoo import api, fields, models


class GnCashClosingRemesaSobranteLine(models.Model):
    _name = "gn.cash.closing.remesa.sobrante.line"
    _description = "Línea de Remesa Sobrante (Efectivo - Cierre de Caja)"
    _order = "sequence, id"

    sequence = fields.Integer(string="Secuencia", default=10)
    sequence_number = fields.Integer(
        string="#",
        compute="_compute_sequence_number",
        help="Número de línea secuencial",
    )

    closing_id = fields.Many2one(
        "gn.cash.closing", string="Cierre de Caja", ondelete="cascade",
    )
    branch_id = fields.Many2one(
        "res.branch",
        related="closing_id.branch_id",
        string="Sucursal",
        readonly=True,
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Diario",
        help="Diario tipo Efectivo (Tipo en Cobros de Cliente = Efectivo) de la sucursal",
    )
    bank_name = fields.Char(string="Banco")

    @api.depends("sequence", "closing_id", "closing_id.remesa_sobrante_line_ids")
    def _compute_sequence_number(self):
        for rec in self:
            rec.sequence_number = 0
        closings = self.mapped("closing_id").filtered(None)
        for closing in closings:
            lines = closing.remesa_sobrante_line_ids.sorted(
                key=lambda l: (l.sequence, l.id)
            )
            for i, ln in enumerate(lines, start=1):
                ln.sequence_number = i

    def _get_bank_account_display(self, bank_account):
        """Formato 'Número de cuenta bancaria': acc_number - bank_name."""
        if not bank_account:
            return ""
        acc_num = bank_account.acc_number or ""
        if bank_account.bank_id:
            return f"{acc_num} - {bank_account.bank_id.name}"
        return acc_num

    @api.onchange("journal_id")
    def _onchange_journal_id(self):
        """Rellena banco y No. Cuenta desde el diario."""
        if self.journal_id:
            if self.journal_id.bank_account_id:
                self.bank_name = self._get_bank_account_display(
                    self.journal_id.bank_account_id
                )
            elif self.journal_id.default_account_id:
                self.bank_name = (
                    self.journal_id.default_account_id.code
                    or self.journal_id.name
                    or ""
                )
            else:
                self.bank_name = self.journal_id.name or ""
            if self.journal_id.default_account_id:
                self.account_number = (
                    self.journal_id.default_account_id.code or ""
                )
            else:
                self.account_number = ""
        else:
            self.bank_name = ""
            self.account_number = ""

    account_number = fields.Char(
        string="No. Cuenta",
        readonly=True,
        help="Cuenta contable del diario (código de la cuenta por defecto)",
    )
    reference = fields.Char(string="Referencia")
    date = fields.Date(string="Fecha")
    amount = fields.Float(string="Monto", digits=(16, 2))
