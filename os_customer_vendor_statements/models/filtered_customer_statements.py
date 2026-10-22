from odoo import fields, models, _

PAYMENT_STATE_SELECTION = [('not_paid', 'Not Paid'),
                           ('in_payment', 'In Payment'),
                           ('paid', 'Paid'),
                           ('partial', 'Partially Paid'),
                           ('reversed', 'Reversed'),
                           ('invoicing_legacy', 'Invoicing App Legacy')]
MOVE_TYPE = [('entry', 'Journal Entry'),
             ('out_invoice', 'Customer Invoice'),
             ('out_refund', 'Customer Credit Note'),
             ('in_invoice', 'Vendor Bill'),
             ('in_refund', 'Vendor Credit Note'),
             ('out_receipt', 'Sales Receipt'),
             ('in_receipt', 'Purchase Receipt')]
STATES = [('draft', 'Draft'),
          ('posted', 'Posted'),
          ('cancel', 'Cancelled')]


class FilteredCustomerStatements(models.Model):
    _name = 'filtered.customer.statements'
    _description = "Filtered Customer Statements"
    _order = 'invoice_date'

    invoice_id = fields.Many2one('account.move', string='Invoice')
    reference = fields.Char('Name')
    company_id = fields.Many2one('res.company', string='Company')
    invoice_date = fields.Date('Invoice Date')
    due_invoice_date = fields.Date('Due Date')
    amount_total_signed = fields.Monetary(related='invoice_id.amount_total_signed', currency_field='currency_id')
    credit_amount = fields.Float("Payments/Credits")
    partner_id = fields.Many2one('res.partner', string='Customer')
    remaining_due_amount = fields.Float("Balance")
    amount_total = fields.Float("Invoices/Debits")
    currency_id = fields.Many2one(related='invoice_id.currency_id')
    payment_id = fields.Many2one('account.payment', string='Payment')
    amount_residual = fields.Monetary(related='invoice_id.amount_residual')
    amount_residual_signed = fields.Monetary(related='invoice_id.amount_residual_signed',
                                             currency_field='currency_id')
    state = fields.Selection(STATES, string='State', readonly=True, copy=False, required=True, default='draft')
    payment_state = fields.Selection(PAYMENT_STATE_SELECTION, string="Payment Status",
                                     readonly=True, copy=False)
    transaction_ids = fields.Many2many(
        string="Transactions", comodel_name='payment.transaction',
        relation='filtered_customer_statements_transaction_rel', column1='invoice_id', column2='transaction_id',
        readonly=True, copy=False)
    move_type = fields.Selection(MOVE_TYPE, string='Type', required=True, store=True, index=True, readonly=True,
                                 default="entry", change_default=True)

    def action_check_record(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoice',
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'target': 'current',

        }


class FilteredVendorStatements(models.Model):
    _name = 'filtered.vendor.statements'
    _description = "Filtered Vendor Statements"
    _order = 'invoice_date'

    invoice_id = fields.Many2one('account.move', string='Invoice')
    reference = fields.Char('Name')
    invoice_date = fields.Date('Invoice Date')
    remaining_due_amount = fields.Float("Balance")
    amount_total = fields.Float("Invoices/Debits")
    payment_id = fields.Many2one('account.payment', string='Payment')
    amount_residual = fields.Monetary(related='invoice_id.amount_residual')
    amount_residual_signed = fields.Monetary(related='invoice_id.amount_residual_signed',
                                             currency_field='currency_id')
    due_invoice_date = fields.Date('Due Date')
    amount_total_signed = fields.Monetary(related='invoice_id.amount_total_signed', currency_field='currency_id')
    credit_amount = fields.Float("Payments/Credits")
    partner_id = fields.Many2one('res.partner', string='Customer')
    payment_state = fields.Selection(PAYMENT_STATE_SELECTION, string="Payment Status",
                                     readonly=True, copy=False)
    company_id = fields.Many2one('res.company', string='Company')
    currency_id = fields.Many2one(related='invoice_id.currency_id')
    state = fields.Selection(STATES, string='State', readonly=True, copy=False, required=True,
                             default='draft')
    move_type = fields.Selection(MOVE_TYPE, string='Type', required=True, store=True, index=True, readonly=True,
                                 default="entry", change_default=True)
    transaction_ids = fields.Many2many(
        string="Transactions", comodel_name='payment.transaction', column1='invoice_id', column2='transaction_id',
        readonly=True, copy=False)

    def action_check_record(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoice',
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'target': 'current',

        }
