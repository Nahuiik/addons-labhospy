# -*- coding: utf-8 -*-
from odoo import api, fields, models


def _get_total_ingresos_for_closing(closing):
    """Obtiene el Total Ingresos del cierre (efectivo + tarjeta + transferencia + anticipos + sobrantes)."""
    if not closing or not closing.date or not closing.branch_id:
        return 0.0
    report = closing.env["report.gn_daily_cash_closing.cash_closing_template"]
    ingresos = report._get_ingresos(closing.date, closing.branch_id.id)
    remesas_sobrantes = sum(closing.remesa_sobrante_line_ids.mapped("amount") or [0])
    return (ingresos.get("total", 0) or 0) + remesas_sobrantes


class GnCashClosingRemesaLine(models.Model):
    _name = "gn.cash.closing.remesa.line"
    _description = "Línea de Remesa Bancaria (Cierre de Caja)"
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
    journal_id = fields.Many2one(
        "account.journal",
        string="Diario",
        domain=[
            ("type", "=", "bank"),
            ("payment_mode", "=", "transferencia"),
        ],
        help="Diario bancario tipo Transferencia con el que se realizó el depósito/transferencia",
    )
    bank_name = fields.Char(string="Banco", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        closing_id = self.env.context.get("default_closing_id")
        if closing_id:
            closing = self.env["gn.cash.closing"].browse(closing_id)
            if closing.exists():
                if "reference" in fields_list or not fields_list:
                    branch_name = closing.branch_id.name or ""
                    res["reference"] = f"CORTE DE CAJA {branch_name}".strip()
                if "amount" in fields_list or not fields_list:
                    res["amount"] = _get_total_ingresos_for_closing(closing)
        return res

    @api.onchange("closing_id")
    def _onchange_closing_id(self):
        """Al cambiar el cierre, rellenar Referencia y Monto con CORTE DE CAJA + Sucursal y Total Ingresos."""
        if self.closing_id:
            branch_name = self.closing_id.branch_id.name or ""
            self.reference = f"CORTE DE CAJA {branch_name}".strip()
            self.amount = _get_total_ingresos_for_closing(self.closing_id)

    @api.depends("sequence", "closing_id", "closing_id.remesa_line_ids")
    def _compute_sequence_number(self):
        for rec in self:
            rec.sequence_number = 0
        closings = self.mapped("closing_id").filtered(None)
        for closing in closings:
            lines = closing.remesa_line_ids.sorted(key=lambda l: (l.sequence, l.id))
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
        """Rellena banco (Número de cuenta bancaria) y No. Cuenta (cuenta contable del diario)."""
        if self.journal_id:
            # Banco = Número de cuenta bancaria del diario (acc_number - bank_name)
            if self.journal_id.bank_account_id:
                self.bank_name = self._get_bank_account_display(self.journal_id.bank_account_id)
            elif self.journal_id.default_account_id:
                self.bank_name = self.journal_id.default_account_id.code or self.journal_id.name or ""
            else:
                self.bank_name = self.journal_id.name or ""
            # No. Cuenta = Cuenta contable del diario
            if self.journal_id.default_account_id:
                self.account_number = self.journal_id.default_account_id.code or ""
            else:
                self.account_number = ""

    account_number = fields.Char(
        string="No. Cuenta",
        readonly=True,
        help="Cuenta contable del diario (código de la cuenta por defecto)",
    )
    reference = fields.Char(string="Referencia")
    date = fields.Date(string="Fecha")
    amount = fields.Float(string="Monto", digits=(16, 2))
