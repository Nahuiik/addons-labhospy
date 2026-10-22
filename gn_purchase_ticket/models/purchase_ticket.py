from odoo import _, api, fields, models
from odoo.exceptions import UserError

class DebitCredit(models.Model):
    _inherit = 'debit.credit'
    _order = 'date desc, id desc'

    is_purchase_ticket = fields.Boolean(string="Purchase Ticket")
    is_purchase_ticket_validated = fields.Boolean(string="Purchase Ticket", default=False, copy=False)
    supplier_id = fields.Many2one(
        'res.partner',
        string="Supplier Name",
        check_company=True,
    )
    purchase_journal_id = fields.Many2one(
        'ir.sequence',
        string="Purchase Sequence",
        help="This will be used to generate the sequence for a purchase ticket",
        domain="[('is_purchase_ticket', '=', True), ('company_id', 'in', [company_id, False])]",
        check_company=True,
    )
    ticket_seq_id = fields.Many2one(
        'ir.sequence',
        string="Purchase Sequence",
        help="This will be used to generate the sequence for a purchase ticket",
        default=lambda self: self._get_ticket_seq(),
        domain="[('is_purchase_ticket', '=', True), ('company_id', 'in', [company_id, False])]",
        check_company=True,
    )
    purchase_seq = fields.Char(string="Purchase Ticket", store=True, readonly=True, copy=False)

    mtype = fields.Selection(
        [
            ('check', 'Cheque'),
            ('transference', 'Transferencia'),
        ],
        string='Cheque/Transferencia',
    )
    m_name = fields.Char('No. Transaccion')
    error_msgm = fields.Char(string="")


    @api.model
    def _get_ticket_seq(self):
        company = self.env.company
        return self.env['ir.sequence'].search([
            ('is_purchase_ticket', '=', True),
            ('move_type', '=', 'purchase_ticket'),
            ('company_id', 'in', [company.id, False]),
        ], limit=1)
    
    
    def action_print_purchase_ticket(self):
        return self.env.ref('gn_purchase_ticket.action_purcharse_ticket_report').report_action(self)
    
    def action_print_check(self):
        return self.env.ref('gn_purchase_ticket.action_check_report').report_action(self)
    
    @api.onchange('mtype', 'journal_id')
    def get_sequence_id(self):
        for record in self:
            if not record.journal_id:
                record.ticket_seq_id = False
                continue
            company = record.company_id or record.env.company
            domain = [
                ('journal_id', '=', record.journal_id.id),
                ('company_id', 'in', [company.id, False]),
            ]
            if record.is_purchase_ticket:
                if record.mtype:
                    domain.append(('move_type', '=', record.mtype))
                else:
                    domain.extend([
                        ('move_type', '=', 'purchase_ticket'),
                        ('is_purchase_ticket', '=', True),
                    ])
            else:
                domain.append(('move_type', '=', record.move_type))
            record.ticket_seq_id = record.env['ir.sequence'].search(domain, limit=1)
    

    def action_validate(self):
        res = super().action_validate()
        for record in self:
            if not record.is_purchase_ticket:
                continue
            if not record.ticket_seq_id:
                raise UserError(_("Please configure a purchase ticket sequence."))
            if record.is_purchase_ticket_validated:
                continue

            record.purchase_seq = record.name
            record.name = record.ticket_seq_id.next_by_id()

            domain = [
                ('journal_id', '=', record.journal_id.id),
                ('company_id', 'in', [record.company_id.id, False]),
            ]
            if record.mtype:
                domain.append(('move_type', '=', record.mtype))
            else:
                domain.extend([
                    ('move_type', '=', 'purchase_ticket'),
                    ('is_purchase_ticket', '=', True),
                ])
            sequence_mtype_id = record.env['ir.sequence'].search(domain, limit=1)
            if sequence_mtype_id:
                record.purchase_seq = sequence_mtype_id.get_next_char(sequence_mtype_id.number_next_actual)

            record.is_purchase_ticket_validated = True
        return res
    
    # @api.onchange('mtype', 'journal_id','move_type')
    def _get_dummy_sequence(self):
        for rec in self:
            if rec.is_purchase_ticket:
                if not rec.ticket_seq_id:
                    sequence_name = rec.ticket_seq_id.display_name if rec.ticket_seq_id else _('Purchase Ticket Sequence')
                    rec.error_msg = _(
                        "No se encontró configuración de secuencia para la secuencia '%s', tipo de movimiento '%s'"
                    ) % (sequence_name, rec.move_type)
                    rec.dummy_name = ''
                else:
                    rec.dummy_name = rec.ticket_seq_id.get_next_char(rec.ticket_seq_id.number_next_actual)
                    rec.error_msg = ''

                    # sequence_id = rec.get_sequence_id()
                    # if not sequence_id:
                    #     rec.error_msg = "No se encontró configuración de secuencia\
                    #                 para el diario '%s',  tipo de movimiento '%s'"%(rec.journal_id.name, rec.move_type)
                    #     rec.purchase_seq = ''
                    # else:
                    #     rec.purchase_seq = sequence_id.prefix + '%%0%sd' % sequence_id.padding % sequence_id.number_next_actual
                    #     rec.error_msg = ''
            else:

                sequence_id = rec.get_sequence_id()
                if not sequence_id:
                    rec.error_msg = _(
                        "No sequence configuration found for journal '%s', move type '%s'"
                    ) % (rec.journal_id.display_name, rec.move_type)
                    rec.dummy_name = ''
                else:
                    rec.dummy_name = sequence_id.get_next_char(sequence_id.number_next_actual)
                    rec.error_msg = ''

    def sequence_c(self):
        sequence_id = self.env['ir.sequence'].search([
            ('move_type', '=', self.mtype),
            ('journal_id', '=', self.journal_id.id),
            ('company_id', 'in', [self.company_id.id, False]),
        ], limit=1)
        return sequence_id        
