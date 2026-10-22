# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo import Command
from odoo.exceptions import UserError


class BankCheck(models.Model):
    _name = 'bank.check'
    _description = 'Check/Transfer'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'gn.banks.document.journal.mixin', 'gn.banks.manual_payment.mixin', 'gn.banks.usd_rate.mixin']
    _order = 'date desc'

    name = fields.Char(string="Name", default="/", copy=False, tracking=4)
    dummy_name = fields.Char(compute='_compute_sequence_preview', string="Dummy Name")
    error_msg = fields.Char(compute='_compute_sequence_preview', string="Error Message")
    description = fields.Text(string="Description", required=True, tracking=5)
    journal_id = fields.Many2one(
        "account.journal",
        "Journal",
        required=True,
        domain="[('type', 'in', ['bank', 'cash'])]",
        tracking=10,
    )
    date = fields.Date(
        string="Check Date",
        help="Effective date for accounting entries",
        required=True,
        tracking=15,
        default=fields.Date.context_today,
    )
    total = fields.Float(string='Total', required=True, tracking=16)
    currency_id = fields.Many2one(
        "res.currency",
        "Currency",
        domain=[('active', '=', True)],
        default=lambda self: self.env.company.currency_id,
        tracking=20,
        required=True,
    )
    company_id = fields.Many2one(
        "res.company",
        "Company",
        default=lambda self: self.env.company,
        required=True,
        tracking=25,
    )
    cancel_date = fields.Date("Cancellation Date", tracking=30)
    check_lines = fields.One2many(
        "bank.check.line",
        "check_id",
        "Check Lines",
        required=True,
        copy=True,
        tracking=35,
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('validated', 'Validated'),
            ('postdated', 'Post-Dated'),
            ('cancel', 'Canceled'),
        ],
        string='State',
        readonly=True,
        default='draft',
        tracking=40,
        copy=False,
    )
    currency_rate = fields.Float(
        string="Currency Rate", digits=(12, 4), tracking=45, default=1.0, readonly=True,
    )
    amount_residual = fields.Float(string='Difference', compute='_compute_residual_amount')
    partner_id = fields.Many2one('res.partner', string="Pay To", tracking=50)
    move_type = fields.Selection(
        [
            ('check', 'Cheque'),
            ('transference', 'Transferencia'),
        ],
        string='Transaction Type',
        required=True,
        default='check',
        tracking=55,
    )
    move_id = fields.Many2one('account.move', string='Account Move', copy=False, tracking=60)
    is_for_payroll = fields.Boolean(string="For Payroll?", tracking=65)
    amount_in_words = fields.Char(compute='amount_word', string='Amount in Word', readonly=True, store=True)
    template_id = fields.Many2one('bank.template', string="Template")
    cheque_format = fields.Many2one('check.format.custom', string="Check Format")
    # Campos analíticos
    analytic_distribution = fields.Json(
        string='Distribución Analítica',
        copy=False,
        default={},
        help="Analytic distribution for this record"
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        check_company=True,
        help="Analytic account for this record"
    )
    analytic_precision = fields.Integer(
        string='Analytic Precision',
        related='company_id.currency_id.decimal_places',
        readonly=True,
        help="Precision for analytic amounts"
    )

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
                'move_type': line.move_type1,
            }
            # Copiar campos analíticos desde la plantilla
            if line.analytic_distribution:
                line_vals['analytic_distribution'] = line.analytic_distribution
            elif line.analytic_account_id:
                line_vals['analytic_account_id'] = line.analytic_account_id.id
            lines.append((0, 0, line_vals))
        self.check_lines = lines
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

    @api.depends('check_lines.amount', 'check_lines.move_type1', 'total')
    def _compute_residual_amount(self):
        for record in self:
            total_debit = sum(record.check_lines.filtered(lambda l: l.move_type1 == 'debit').mapped('amount'))
            total_credit = sum(record.check_lines.filtered(lambda l: l.move_type1 == 'credit').mapped('amount'))
            record.amount_residual = round(record.total - (total_debit - total_credit), 2)

    @api.onchange('currency_id', 'date')
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

    def unlink(self):
        for record in self:
            if record.name != '/' and not self._context.get('force_delete'):
                raise UserError(_("You cannot delete a record which has been validated once."))
            record.check_lines.unlink()
        return super().unlink()

    @api.depends('total', 'currency_id')
    def amount_word(self):
        for record in self:
            record.amount_in_words = ''
            if record.currency_id:
                record.amount_in_words = record.currency_id.amount_to_text(record.total)

    def _get_report_base_filename(self):
        """Return the filename base used when printing checks."""
        self.ensure_one()
        if self.name and self.name != '/':
            return self.name
        return 'bank_check'

    def _ensure_currency_rate(self):
        for record in self:
            if not record.currency_rate:
                record.currency_rate = 1.0
            if record.currency_id and record.currency_id != record.company_id.currency_id:
                record.currency_rate = record.currency_id.with_context(date=record.date).rate
            else:
                record.currency_rate = 1.0

    def action_set_to_draft(self):
        for record in self.filtered(lambda r: r.state == 'cancel'):
            record.state = 'draft'
            if record.move_id:
                record.move_id.button_draft()

    def action_cancel(self):
        for record in self:
            if not record.move_id:
                if not record.name or record.name == '/':
                    sequence = record._get_sequence()
                    if not sequence:
                        raise UserError(
                            "No sequence configuration found for journal '%s', move type '%s'" %
                            (record.journal_id.display_name, record.move_type)
                        )
                    record.name = sequence.next_by_id()
                values = {
                    'journal_id': record.journal_id.id,
                    'date': record.date,
                    'ref': record.partner_id.name,
                    'state': 'draft',
                    'name': record.name,
                    'sequence_generated': True,
                    'move_type': 'entry',
                }
                record.move_id = record.env['account.move'].create(values)
            if record.move_id.state != 'draft':
                record.move_id.button_draft()
            record.move_id.button_cancel()
            record.state = 'cancel'

    def action_validate(self):
        for record in self:
            if not record.check_lines:
                raise UserError(_("Please add some line before validate!"))
            if record.total <= 0:
                raise UserError(_("Negative or zero total is not allowed"))
            if round(record.amount_residual, 2) != 0.0:
                raise UserError(_("Line total must be same as total amount!"))

            record._ensure_currency_rate()

            if not record.move_id and (not record.name or record.name == '/'):
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

    def _create_or_update_move(self):
        self.ensure_one()
        account_move = self.env['account.move']
        if not self.move_id:
            values = {
                'journal_id': self.journal_id.id,
                'date': self.date,
                'ref': self.partner_id.name,
                'state': 'draft',
                'sequence_generated': True,
                'move_type': 'entry',
                'name': self.name,
            }
            move = account_move.create(values)
        else:
            move = self.move_id
            move.write({'date': self.date, 'ref': self.partner_id.name})
            if move.state != 'draft':
                raise UserError(_("Linked move is not in draft state. Please check."))
            move.line_ids.unlink()

        company_currency = self.company_id.currency_id
        commands = [Command.clear()]

        payment_account = self._get_manual_payment_account_from_journal(
            self.journal_id, is_outbound=True
        )
        payment_account_id = payment_account.id if payment_account else False

        credit_vals = {
            'name': self.partner_id.name,
            'partner_id': self.partner_id.id,
            'account_id': payment_account_id,
            'credit': self.total * self.currency_rate,
            'debit': 0.0,
            'date': self.date,
        }
        if self.currency_id != company_currency:
            credit_vals.update({
                'currency_id': self.currency_id.id,
                'amount_currency': -self.total,
            })

        for line in self.check_lines:
            line_vals = {
                'name': line.name or self.partner_id.name,
                'account_id': line.account_id.id,
                'partner_id': line.partner_id.id,
                'date': self.date,
            }
            # Agregar campos analíticos
            if line.analytic_distribution:
                line_vals['analytic_distribution'] = line.analytic_distribution
            elif line.analytic_account_id:
                line_vals['analytic_account_id'] = line.analytic_account_id.id
            if line.move_type1 == 'debit':
                line_vals.update({
                    'debit': line.amount * self.currency_rate,
                    'credit': 0.0,
                })
                if self.currency_id != company_currency:
                    line_vals.update({
                        'currency_id': self.currency_id.id,
                        'amount_currency': line.amount,
                    })
            else:
                line_vals.update({
                    'debit': 0.0,
                    'credit': line.amount * self.currency_rate,
                })
                if self.currency_id != company_currency:
                    line_vals.update({
                        'currency_id': self.currency_id.id,
                        'amount_currency': -line.amount,
                    })
            commands.append(Command.create(line_vals))

        commands.append(Command.create(credit_vals))

        move.with_context(check_move_validity=False).write({'line_ids': commands})
        move.action_post()
        return move


class BankCheckLine(models.Model):
    _name = 'bank.check.line'
    _description = "Bank Check Lines"

    check_id = fields.Many2one('bank.check', 'Check')
    partner_id = fields.Many2one('res.partner', 'Partner', domain="['|', ('company_id', '=', False), ('company_id', '=', parent.company_id)]")
    account_id = fields.Many2one('account.account', 'Account', required=True)
    name = fields.Char('Description')
    amount = fields.Float('Amount', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency')
    move_type = fields.Selection(related='check_id.move_type', string='Debit/Credit Check', store=True)
    move_type1 = fields.Selection([
        ('debit', 'Debit'),
        ('credit', 'Credit')
    ], string='Check Debit/Credit', required=True, default='debit')
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
        related='check_id.company_id.currency_id.decimal_places',
        readonly=True,
        help="Precision for analytic amounts"
    )
