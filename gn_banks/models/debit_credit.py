# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo import Command
from odoo.exceptions import UserError


class DebitCredit(models.Model):
    _name = 'debit.credit'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'gn.banks.document.journal.mixin', 'gn.banks.manual_payment.mixin', 'gn.banks.usd_rate.mixin']
    _description = "Debit/Credit"
    _order = 'date desc'
    _check_company_auto = True

    name = fields.Char(string="Name", default="/", copy=False, tracking=4)
    dummy_name = fields.Char(compute='_compute_sequence_preview', string="Dummy Name")
    error_msg = fields.Char(compute='_compute_sequence_preview', string="Error Message")
    description = fields.Text(string="Description", required=True, tracking=5)
    journal_id = fields.Many2one(
        "account.journal",
        "Journal",
        required=True,
        domain="[('type', 'in',['bank','cash'])]",
        tracking=10,
        check_company=True,
    )
    date = fields.Date(string="Date", help="Effective date for accounting entries", required=True, tracking=15)
    currency_id = fields.Many2one(
        "res.currency",
        "Currency",
        domain=[('active', '=', True)],
        default=lambda self: self.env.company.currency_id,
        tracking=20,
        required=True,
    )
    total = fields.Monetary(string='Total', required=True, currency_field='currency_id')
    company_id = fields.Many2one(
        "res.company",
        "Company",
        default=lambda self: self.env.company,
        required=True,
        tracking=25,
    )
    state = fields.Selection(
        [('draft', 'draft'), ('validated', 'Validated'), ('cancel', "Cancelled")],
        string="Status",
        default='draft',
        copy=False,
        tracking=30,
    )
    debit_line_ids = fields.One2many("debit.credit.line", "debit_id", "Detalle de debito/credito", copy=True, tracking=35)
    amount_residual = fields.Float(compute='_compute_residual_amount', string='Difference', store=True)
    move_id = fields.Many2one('account.move', string='Account Move', copy=False, tracking=38)
    bank_invoice_id = fields.Many2one(
        'account.move',
        string='Factura Banco (reporte)',
        copy=False,
        help='Factura de proveedor creada desde CCF 03 para reportes; no genera asiento.',
    )
    move_type = fields.Selection(
        [
            ('debit', 'Débito'),
            ('credit', 'Crédito'),
            ('deposit', 'Depósito'),
            ('credit_card', 'POS Settlement'),
        ],
        string='Transaction Type',
        required=True,
        tracking=40,
    )
    is_advance = fields.Boolean(string="Customer Advance", tracking=45)
    partner_id = fields.Many2one('res.partner', string="Customer", tracking=50, check_company=True)
    total_debit = fields.Float(compute='_compute_totals', string="Total Debit", store=True)
    total_credit = fields.Float(compute='_compute_totals', string="Total Credit", store=True)
    currency_rate = fields.Float(
        "Exchange rate", digits=(12, 4), tracking=55, default=1.0, readonly=True,
    )
    amount_in_words = fields.Char(compute='amount_word', string='Amount in Word', store=True)
    template_id = fields.Many2one('bank.template', string="Template", check_company=True)
    document_ids = fields.One2many('bank.documents', 'bank_debit_id', string="Documents")
    # Campos analíticos
    analytic_distribution = fields.Json(
        string='Distribución Analítica',
        copy=False,
        default={},
        help="Analytic distribution for this record"
    )
    analytic_precision = fields.Integer(
        store=False,
        default=lambda self: self.env['decimal.precision'].precision_get("Percentage Analytic"),
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        check_company=True,
        help="Analytic account for this record"
    )

    def validate_movements(self):
        for record in self:
            record.action_cancel()
            record.action_set_to_draft()
            record.action_validate()

    @api.onchange('template_id')
    def change_tempate_id(self):
        template = self.template_id
        if not template:
            return
        self.update({
            'partner_id': template.partner_id.id,
            'journal_id': template.journal_id.id,
            'total': template.total,
            'description': template.description,
            'currency_id': template.currency_id.id,
            'currency_rate': template.currency_rate,
            'move_type': template.move_type,
            'company_id': template.company_id.id,
        })
        lines = []
        for line in template.template_lines:
            line_vals = {
                'partner_id': line.partner_id.id,
                'account_id': line.account_id.id,
                'name': line.name,
                'amount': line.amount,
                'currency_id': line.currency_id.id,
            }
            # Copiar campos analíticos desde la plantilla
            if line.analytic_distribution:
                line_vals['analytic_distribution'] = line.analytic_distribution
            elif line.analytic_account_id:
                line_vals['analytic_account_id'] = line.analytic_account_id.id
            lines.append((0, 0, line_vals))
        self.debit_line_ids = lines
        # Copiar campos analíticos del encabezado desde la plantilla
        if template.analytic_distribution:
            self.analytic_distribution = template.analytic_distribution
        elif template.analytic_account_id:
            self.analytic_account_id = template.analytic_account_id.id

    def _get_sequence(self):
        self.ensure_one()
        return self.env['ir.sequence'].search([
            ('move_type', '=', self.move_type),
            ('journal_id', '=', self.journal_id.id),
        ], limit=1)

    @api.depends('journal_id', 'move_type')
    def _compute_sequence_preview(self):
        for record in self:
            record.dummy_name = False
            record.error_msg = False
            if not record.journal_id or not record.move_type:
                continue
            sequence = record._get_sequence()
            if not sequence:
                record.error_msg = _(
                    "No sequence configuration found for journal '%s', move type '%s'",
                    record.journal_id.display_name,
                    record.move_type,
                )
            else:
                record.dummy_name = sequence.get_next_char(sequence.number_next_actual)

    @api.onchange('journal_id', 'move_type')
    def change_journal_move_type(self):
        if self.journal_id and self.move_type:
            self._compute_sequence_preview()

    def unlink(self):
        for record in self:
            if record.name != '/' and not self._context.get('force_delete'):
                raise UserError(_("You cannot delete a record which has been validated once."))
            record.debit_line_ids.unlink()
        return super().unlink()

    @api.depends('total', 'debit_line_ids.amount', 'debit_line_ids.type', 'move_type')
    def _compute_residual_amount(self):
        for record in self:
            debit_total = sum(record.debit_line_ids.filtered(lambda l: l.type == 'debit').mapped('amount'))
            credit_total = sum(record.debit_line_ids.filtered(lambda l: l.type == 'credit').mapped('amount'))
            if record.move_type in ['debit', 'credit_card']:
                record.amount_residual = record.total - (debit_total - credit_total)
            elif record.move_type in ['deposit', 'credit']:
                record.amount_residual = record.total - abs(credit_total - debit_total)
            else:
                line_total = sum(record.debit_line_ids.mapped('amount'))
                record.amount_residual = round(record.total - line_total, 2)

    @api.depends('move_type', 'debit_line_ids.amount', 'debit_line_ids.type')
    def _compute_totals(self):
        for record in self:
            record.total_debit = sum(record.debit_line_ids.filtered(lambda l: l.type == 'debit').mapped('amount'))
            record.total_credit = sum(record.debit_line_ids.filtered(lambda l: l.type == 'credit').mapped('amount'))

    @api.onchange("currency_id", "date")
    def change_currency_id(self):
        for record in self:
            if not record.currency_id:
                record.currency_rate = 1.0
            elif record.currency_id != record.company_id.currency_id:
                record.currency_rate = record.currency_id.with_context(date=record.date).rate
            else:
                record.currency_rate = 1.0

    @api.onchange("journal_id")
    def onchangejournal(self):
        for record in self:
            if not record.journal_id:
                continue
            if record.journal_id.currency_id:
                record.currency_id = record.journal_id.currency_id
            else:
                record.currency_id = record.company_id.currency_id

    def action_cancel(self):
        for record in self:
            if not record.move_id:
                continue
            if record.move_id.state != 'draft':
                record.move_id.button_draft()
            record.move_id.button_cancel()
            record.state = 'cancel'

    def action_set_to_draft(self):
        for record in self.filtered(lambda r: r.state == 'cancel'):
            record.state = 'draft'
            if record.move_id:
                record.move_id.button_draft()

    def _ensure_currency_rate(self):
        for record in self:
            if not record.currency_rate:
                record.currency_rate = 1.0
            if record.currency_id and record.currency_id != record.company_id.currency_id:
                record.currency_rate = record.currency_id.with_context(date=record.date).rate
            else:
                record.currency_rate = 1.0

    def action_validate(self):
        for record in self:
            if not record.debit_line_ids:
                raise UserError(_("Please add some line before validate!"))
            if record.total <= 0:
                raise UserError(_("Negative or zero total is not allowed"))
            if round(record.amount_residual, 2) != 0.0:
                raise UserError(_("Line total must be the same as total amount!"))

            record._ensure_currency_rate()

            if not record.move_id:
                sequence = record._get_sequence()
                if not sequence:
                    raise UserError(
                        "No sequence configuration found for journal '%s', move type '%s'" %
                        (record.journal_id.display_name, record.move_type)
                    )
                record.name = sequence.next_by_id()

            move = record._create_or_update_move()
            record.move_id = move.id
            record.state = 'validated'

    def _get_manual_payment_account(self):
        self.ensure_one()
        is_outbound = self.move_type in ['debit', 'credit_card']
        account = self._get_manual_payment_account_from_journal(
            self.journal_id, is_outbound=is_outbound
        )
        return account.id if account else False

    def _create_or_update_move(self):
        self.ensure_one()
        account_move = self.env['account.move']
        if not self.move_id:
            values = {
                'journal_id': self.journal_id.id,
                'date': self.date,
                'ref': self.description,
                'move_type': 'entry',
                'sequence_generated': True,
                'name': self.name,
            }
            move = account_move.create(values)
        else:
            move = self.move_id
            move.write({'date': self.date, 'ref': self.description})
            if move.state != 'draft':
                raise UserError(_("Linked move is not in draft state. Please check."))
            move.line_ids.unlink()

        manual_account = self._get_manual_payment_account()

        company_currency = self.company_id.currency_id
        commands = [Command.clear()]

        def _amounts(amount):
            if self.currency_id != company_currency:
                return {
                    'currency_id': self.currency_id.id,
                    'amount_currency': amount,
                }
            return {}

        if self.move_type in ['debit', 'credit_card']:
            credit_vals = {
                'name': self.description,
                'account_id': manual_account,
                'credit': self.total * self.currency_rate,
                'debit': 0.0,
                'date': self.date,
            }
            credit_vals.update(_amounts(-self.total))
            commands.append(Command.create(credit_vals))

            for line in self.debit_line_ids:
                vals = {
                    'name': line.name or self.name,
                    'account_id': line.account_id.id,
                    'partner_id': line.partner_id.id,
                    'date': self.date,
                }
                # Agregar campos analíticos
                if line.analytic_distribution:
                    vals['analytic_distribution'] = line.analytic_distribution
                elif line.analytic_account_id:
                    vals['analytic_account_id'] = line.analytic_account_id.id
                if line.type == 'debit':
                    vals.update({'debit': line.amount * self.currency_rate, 'credit': 0.0})
                    vals.update(_amounts(line.amount))
                else:
                    vals.update({'debit': 0.0, 'credit': line.amount * self.currency_rate})
                    vals.update(_amounts(-line.amount))
                commands.append(Command.create(vals))
        else:
            debit_vals = {
                'name': self.name,
                'account_id': manual_account,
                'credit': 0.0,
                'debit': self.total * self.currency_rate,
                'date': self.date,
            }
            debit_vals.update(_amounts(self.total))
            commands.append(Command.create(debit_vals))

            for line in self.debit_line_ids:
                vals = {
                    'name': line.name or self.name,
                    'account_id': line.account_id.id,
                    'partner_id': line.partner_id.id,
                    'date': self.date,
                }
                # Agregar campos analíticos
                if line.analytic_distribution:
                    vals['analytic_distribution'] = line.analytic_distribution
                elif line.analytic_account_id:
                    vals['analytic_account_id'] = line.analytic_account_id.id
                if line.type == 'credit':
                    vals.update({'debit': 0.0, 'credit': line.amount * self.currency_rate})
                    vals.update(_amounts(-line.amount))
                else:
                    vals.update({'debit': line.amount * self.currency_rate, 'credit': 0.0})
                    vals.update(_amounts(line.amount))
                commands.append(Command.create(vals))

        move.with_context(check_move_validity=False).write({'line_ids': commands})
        move.action_post()
        return move

    @api.depends('total', 'currency_id')
    def amount_word(self):
        for record in self:
            record.amount_in_words = ''
            if record.currency_id:
                record.amount_in_words = record.currency_id.amount_to_text(record.total)

    def print_voucher(self):
        return self.env.ref('gn_banks.banks_deposit_print').report_action(self.move_id)


class DebitCreditLine(models.Model):
    _name = 'debit.credit.line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Debit Credit Line"
    _order = 'account_id desc'

    debit_id = fields.Many2one('debit.credit', string="Line Debit/Credit", tracking=5)
    partner_id = fields.Many2one('res.partner', 'Company', tracking=10)
    account_id = fields.Many2one('account.account', string='Account', required=True, tracking=15)
    name = fields.Char('Description', tracking=20)
    amount = fields.Float('Amount', required=True, tracking=25)
    currency_id = fields.Many2one('res.currency', string='Currency', tracking=30)
    move_type = fields.Selection(related='debit_id.move_type', depends=['debit_id.move_type'], string="Move Type", tracking=40, store=True)
    type = fields.Selection([('credit', 'Credit'), ('debit', 'Debit')], string="Type")
    # Campos analíticos
    analytic_distribution = fields.Json(
        string='Distribución Analítica',
        copy=False,
        default={},
        help="Analytic distribution for this line"
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        check_company=True,
        help="Analytic account for this line"
    )
    analytic_precision = fields.Integer(
        string='Analytic Precision',
        related='debit_id.company_id.currency_id.decimal_places',
        readonly=True,
        help="Precision for analytic amounts"
    )

    @api.onchange('account_id')
    def change_get_type(self):
        for record in self:
            if record.move_type in ('deposit', 'credit'):
                record.type = 'credit'
            else:
                record.type = 'debit'
