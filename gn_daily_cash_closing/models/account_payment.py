# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    closing_line_sequence = fields.Integer(
        string="#",
        compute="_compute_closing_line_sequence",
        store=True,
        help="Número de secuencia en listas del Cierre de Caja",
    )

    payment_display_type = fields.Char(
        string="Tipo",
        compute="_compute_payment_display_type",
        help="Efectivo, Tarjeta o Transferencia según el diario o tipo de pago",
    )

    @api.depends()
    def _compute_closing_line_sequence(self):
        """Número de fila (1, 2, 3...) cuando se muestra en listas del Cierre de Caja."""
        for rec in self:
            rec.closing_line_sequence = 0

        # Buscar el cierre que contiene estos pagos (no depender del context active_id)
        closing = self.env["gn.cash.closing"].search([
            "|", "|", "|", "|",
            ("payment_posted_ids", "in", self.ids),
            ("payment_cancelled_ids", "in", self.ids),
            ("advance_ids", "in", self.ids),
            ("advance_presupuesto_ids", "in", self.ids),
            ("advance_prefactura_ids", "in", self.ids),
        ], limit=1)
        if not closing:
            return

        seq_by_id = {}
        for field_name in (
            "payment_posted_ids", "payment_cancelled_ids", "advance_ids",
            "advance_presupuesto_ids", "advance_prefactura_ids",
        ):
            for i, payment in enumerate(getattr(closing, field_name), start=1):
                seq_by_id[payment.id] = i

        for rec in self:
            rec.closing_line_sequence = seq_by_id.get(rec.id, 0)

    @api.depends("journal_id", "journal_id.type")
    def _compute_payment_display_type(self):
        for payment in self:
            payment.payment_display_type = self._get_payment_display_type(payment)

    @api.model
    def _get_payment_display_type(self, payment):
        """Devuelve Efectivo, Tarjeta o Transferencia.
        Usa payment_move_type (gts_multiple_invoice_payment_currency) si existe,
        sino journal payment_mode (gn_payment_extra) o journal.type como fallback.
        """
        # 1. payment_move_type de gts_multiple_invoice_payment_currency (pagos outbound)
        if "payment_move_type" in payment._fields and payment.payment_move_type:
            labels = {
                "cash": "Efectivo",
                "transference": "Transferencia",
                "check": "Cheque",
                "otro": "Otro",
            }
            if payment.payment_move_type in labels:
                return labels[payment.payment_move_type]
        # payment_move_type_dep = 'deposit' para inbound no distingue tipo, usar journal
        # 2. journal payment_mode de gn_payment_extra
        journal = payment.journal_id
        if journal:
            if hasattr(journal, "payment_mode") and journal.payment_mode in (
                "efectivo",
                "tarjeta",
                "transferencia",
            ):
                labels = {
                    "efectivo": "Efectivo",
                    "tarjeta": "Tarjeta",
                    "transferencia": "Transferencia",
                }
                return labels.get(journal.payment_mode, "")
            # 3. Fallback por journal.type
            if journal.type == "cash":
                return "Efectivo"
            if journal.type == "bank":
                if hasattr(journal, "is_credit_card") and journal.is_credit_card:
                    return "Tarjeta"
                return "Transferencia"
        return ""
