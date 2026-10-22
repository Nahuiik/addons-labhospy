from odoo import api, fields, models

class SaleOrder(models.Model):
    _inherit = "account.move"

    overdue_invoice_count = fields.Integer(
        compute="_compute_overdue_invoice_count_amount",
        string="# of Overdue Invoices",
    )
    
    overdue_invoice_amount = fields.Float(
        compute="_compute_overdue_invoice_count_amount",
        string="Overdue Invoices Residual",
        help="Overdue invoices total residual amount of the invoicing partner "
        "in company currency.",
    )

    @api.depends("partner_id", "company_id")
    def _compute_overdue_invoice_count_amount(self):
        for order in self:
            count = amount = 0
            partner = order.partner_id
            if partner:
                count, amount = partner._prepare_overdue_invoice_count_amount(
                    order.company_id.id
                )
            order.overdue_invoice_count = count
            order.overdue_invoice_amount = amount

    def jump_to_overdue_invoices(self):
        self.ensure_one()
        action = self.partner_id._prepare_jump_to_overdue_invoices(
            self.company_id.id
        )
        return action
