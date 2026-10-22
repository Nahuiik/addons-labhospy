from odoo import models, fields, api


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    sequence_id = fields.Many2one(
        'ir.sequence',
        string='Entry Sequence',
        help="This field contains the information related to the numbering of the journal entries of this journal.",
        copy=False,
    )
    refund_sequence_id = fields.Many2one(
        'ir.sequence',
        string='Credit Note Entry Sequence',
        help="This field contains the information related to the numbering of the credit note entries of this journal.",
        copy=False,
    )
    sequence_number_next = fields.Integer(
        string='Numero siguiente',
        help='The next sequence number will be used for the next invoice.',
        compute='_compute_seq_number_next',
        inverse='_inverse_seq_number_next',
    )
    refund_sequence_number_next = fields.Integer(
        string='Credit Notes Next Number',
        help='The next sequence number will be used for the next credit note.',
        compute='_compute_refund_seq_number_next',
        inverse='_inverse_refund_seq_number_next',
    )
    debit_sequence_id = fields.Many2one(
        'ir.sequence',
        string='Debit Note Entry Sequence',
        help="This field contains the information related to the numbering of the debit note entries of this journal.",
        copy=False,
    )
    debit_sequence_number_next = fields.Integer(
        string='Debit Notes Next Number',
        help='The next sequence number will be used for the next debit note.',
        compute='_compute_debit_seq_number_next',
        inverse='_inverse_debit_seq_number_next',
    )

    # do not depend on 'sequence_id.date_range_ids', because
    # sequence_id._get_current_sequence() may invalidate it!
    @api.depends('sequence_id.use_date_range', 'sequence_id.number_next_actual')
    def _compute_seq_number_next(self):
        '''Compute 'sequence_number_next' according to the current sequence in use,
        an ir.sequence or an ir.sequence.date_range.
        '''
        for journal in self:
            if journal.sequence_id:
                sequence = journal.sequence_id._get_current_sequence()
                journal.sequence_number_next = sequence.number_next_actual
            else:
                journal.sequence_number_next = 1

    def _inverse_seq_number_next(self):
        '''Inverse 'sequence_number_next' to edit the current sequence next number.
        '''
        for journal in self:
            if journal.sequence_id and journal.sequence_number_next:
                sequence = journal.sequence_id._get_current_sequence()
                sequence.sudo().number_next = journal.sequence_number_next

    # do not depend on 'refund_sequence_id.date_range_ids', because
    # refund_sequence_id._get_current_sequence() may invalidate it!
    @api.depends('refund_sequence_id.use_date_range', 'refund_sequence_id.number_next_actual')
    def _compute_refund_seq_number_next(self):
        '''Compute 'sequence_number_next' according to the current sequence in use,
        an ir.sequence or an ir.sequence.date_range.
        '''
        for journal in self:
            if journal.refund_sequence_id and journal.refund_sequence:
                sequence = journal.refund_sequence_id._get_current_sequence()
                journal.refund_sequence_number_next = sequence.number_next_actual
            else:
                journal.refund_sequence_number_next = 1

    def _inverse_refund_seq_number_next(self):
        '''Inverse 'refund_sequence_number_next' to edit the current sequence next number.
        '''
        for journal in self:
            if journal.refund_sequence_id and journal.refund_sequence and journal.refund_sequence_number_next:
                sequence = journal.refund_sequence_id._get_current_sequence()
                sequence.sudo().number_next = journal.refund_sequence_number_next

    # do not depend on 'debit_sequence_id.date_range_ids', because
    # debit_sequence_id._get_current_sequence() may invalidate it!
    @api.depends('debit_sequence_id.use_date_range', 'debit_sequence_id.number_next_actual')
    def _compute_debit_seq_number_next(self):
        '''Compute 'debit_sequence_number_next' according to the current sequence in use,
        an ir.sequence or an ir.sequence.date_range.
        '''
        for journal in self:
            if journal.debit_sequence_id:
                sequence = journal.debit_sequence_id._get_current_sequence()
                journal.debit_sequence_number_next = sequence.number_next_actual
            else:
                journal.debit_sequence_number_next = 1

    def _inverse_debit_seq_number_next(self):
        '''Inverse 'debit_sequence_number_next' to edit the current sequence next number.
        '''
        for journal in self:
            if journal.debit_sequence_id and journal.debit_sequence_number_next:
                sequence = journal.debit_sequence_id._get_current_sequence()
                sequence.sudo().number_next = journal.debit_sequence_number_next
    payment_debit_account_id = fields.Many2one(
        comodel_name='account.account',
        check_company=True,
        copy=False,
        ondelete='restrict',
        help="Incoming payments entries triggered by invoices/refunds will be posted on the Outstanding Receipts Account "
             "and displayed as blue lines in the bank reconciliation widget. During the reconciliation process, concerned "
             "transactions will be reconciled with entries on the Outstanding Receipts Account instead of the "
             "receivable account.",
        string='Outstanding Receipts Account',
        domain="[('account_type', '=', default_account_type),"
               "('account_type', 'not in', ('asset_receivable', 'liability_payable'))]",
    )

    payment_credit_account_id = fields.Many2one(
        comodel_name='account.account',
        check_company=True,
        copy=False,
        ondelete='restrict',
        help="Outgoing payments entries triggered by bills/credit notes will be posted on the Outstanding Payments Account "
             "and displayed as blue lines in the bank reconciliation widget. During the reconciliation process, concerned "
             "transactions will be reconciled with entries on the Outstanding Payments Account instead of the "
             "payable account.",
        string='Outstanding Payments Account',
        domain="[('account_type', '=', default_account_type),"
               "('account_type', 'not in', ('asset_receivable', 'liability_payable'))]",
    )

    suspense_account_id = fields.Many2one(
        comodel_name='account.account',
        check_company=True,
        ondelete='restrict',
        readonly=False,
        store=True,
        compute='_compute_suspense_account_id',
        help="Bank statements transactions will be posted on the suspense account until the final reconciliation "
             "allowing finding the right account.",
        string='Suspense Account',
        domain="[('account_type', '=', default_account_type),"
               "('account_type', 'not in', ('asset_receivable', 'liability_payable'))]",
    )
