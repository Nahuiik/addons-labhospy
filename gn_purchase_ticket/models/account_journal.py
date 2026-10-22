from odoo import models, fields


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    is_purchase_ticket = fields.Boolean(string="Purchase Tickets")
    purchase_ticket_seq = fields.Many2one(
        'ir.sequence',
        string="Purchase Ticket Seq",
        domain="[('is_purchase_ticket', '=', True), ('company_id', 'in', [company_id, False])]",
        check_company=True,
    )
    # retention_seq = fields.Many2one('ir.sequence', string="Retention")
    purchase_sequence_id = fields.Many2one(
        'ir.sequence',
        string="Boleta de Compra",
        domain="[('is_purchase_ticket', '=', True), ('company_id', 'in', [company_id, False])]",
        check_company=True,
    )
    # # retention_seq = fields.Many2one('ir.sequence', string="Retention")
