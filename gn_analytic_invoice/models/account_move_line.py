# -*- coding: utf-8 -*-
from odoo import api, fields, models


_VENDOR_BILL_TYPES = ("in_invoice", "in_refund")
_CUSTOMER_INVOICE_TYPES = ("out_invoice", "out_refund")


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    analytic_dist_template_id = fields.Many2one(
        "analytic.distribution.template",
        string="Plantilla distribucion",
        ondelete="set null",
    )

    def _is_vendor_bill_line(self):
        self.ensure_one()
        move = self.move_id
        return bool(move) and move.move_type in _VENDOR_BILL_TYPES

    @api.onchange("analytic_dist_template_id")
    def _onchange_analytic_dist_template_id(self):
        if not self.analytic_dist_template_id:
            return
        if not self._is_vendor_bill_line():
            return
        self.analytic_distribution = (
            self.analytic_dist_template_id.analytic_distribution
        )

    @api.depends("account_id", "partner_id", "product_id", "move_id.journal_id")
    def _compute_analytic_distribution(self):
        """En facturas de cliente la analitica se toma del diario, no de las
        reglas de account.analytic.distribution.model.

        Esas reglas suelen configurarse para compras (ej. centros Arce / Metro) y Odoo
        las aplica tambien en ventas y out_invoice por partner/producto.
        En compras (in_invoice / in_refund) se mantiene el estandar.
        """
        aml_customer = self.filtered(
            lambda l: l.move_id and l.move_id.move_type in _CUSTOMER_INVOICE_TYPES
        )
        super(AccountMoveLine, self - aml_customer)._compute_analytic_distribution()
        for line in aml_customer:
            if line.display_type == "product" or not line.move_id.is_invoice(
                include_receipts=True
            ):
                related = line._related_analytic_distribution()
                journal_dist = line.move_id.journal_id.analytic_distribution or False
                line.analytic_distribution = (
                    related or journal_dist or line.analytic_distribution
                )
