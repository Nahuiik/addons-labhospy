from odoo import models, fields, api


class BankTemplate(models.Model):
    _name = 'bank.template'
    _description = "Bank Templates"
    _inherit = ['gn.banks.usd_rate.mixin']
    
    partner_id = fields.Many2one('res.partner', string="Partner")
    journal_id = fields.Many2one("account.journal", string="Journal", required=True)
    total = fields.Float(string='Total', required=True)
    description = fields.Text("Description")
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    name = fields.Char(string="Name", required=True)
    template_lines = fields.One2many("bank.template.line", "template_id", "Template Lines", required=True)
    currency_rate = fields.Float(
        "Currency Rate", digits=(12, 4), default=1.0, readonly=True,
    )
    move_type = fields.Selection([
        ('check', 'Cheque'),
        ('transference', 'Transferencia'),
        ('debit', 'Débito'),
        ('credit', 'Crédito'),
        ('deposit', 'Depósito'),
    ], string='Transaction Type', required=True, default='check')
    company_id = fields.Many2one("res.company", "Empresa", 
                                 default=lambda self: self.env.company, required=True)
    # Campos analíticos
    analytic_distribution = fields.Json(
        string='Distribución Analítica',
        copy=False,
        default={},
        help="Analytic distribution for this template"
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        check_company=True,
        help="Analytic account for this template"
    )
    analytic_precision = fields.Integer(
        string='Analytic Precision',
        related='company_id.currency_id.decimal_places',
        readonly=True,
        help="Precision for analytic amounts"
    )

    @api.onchange('currency_id', 'company_id')
    def _onchange_currency_or_company(self):
        """Ensure the exchange rate is consistent when currency or company changes."""
        self._ensure_currency_rate()

    def _ensure_currency_rate(self):
        """Force a rate of 1 for the company currency and fetch current rate otherwise."""
        for record in self:
            company = record.company_id or record.env.company
            company_currency = company.currency_id
            if not record.currency_id:
                record.currency_id = company_currency
            if record.currency_id == company_currency:
                record.currency_rate = 1.0
            else:
                date = fields.Date.context_today(record)
                rate = record.env['res.currency']._get_conversion_rate(
                    record.currency_id, company_currency, company, date,
                )
                record.currency_rate = rate or 1.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company_id = vals.get('company_id') or self.env.company.id
            vals.setdefault('company_id', company_id)
            company = self.env['res.company'].browse(company_id)
            currency_id = vals.get('currency_id') or company.currency_id.id
            vals.setdefault('currency_id', currency_id)
            if not vals.get('currency_rate') and currency_id == company.currency_id.id:
                vals['currency_rate'] = 1.0
        records = super().create(vals_list)
        records._ensure_currency_rate()
        return records

    def write(self, vals):
        res = super().write(vals)
        trigger_fields = {'currency_id', 'company_id'}
        if trigger_fields.intersection(vals) and 'currency_rate' not in vals:
            self._ensure_currency_rate()
        return res


class BankTemplateLine(models.Model):
    _name = 'bank.template.line'
    _description = "Bank Template Lines"

    template_id = fields.Many2one('bank.template', string='Template')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='template_id.company_id',
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one('res.partner', 'Partner', domain="['|', ('company_id', '=', False), ('company_id', '=', parent.company_id)]")
    account_id = fields.Many2one('account.account', 'Account', required=True)
    name = fields.Char('Description')
    amount = fields.Float('Amount', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency')
    move_type = fields.Selection(related='template_id.move_type', string='Bank Debit/Credit', required=True)
    move_type1 = fields.Selection([('debit', 'Debit'),('credit', 'Credit')], string='Bank Debit-Credit', required=True,default='debit')
    # Campos analíticos
    analytic_distribution = fields.Json(
        string='Distribución Analítica',
        copy=False,
        default={},
        help="Analytic distribution for this template line"
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        check_company=True,
        domain="[('company_id', '=', parent.company_id)]",
        help="Analytic account for this template line"
    )
    analytic_precision = fields.Integer(
        string='Analytic Precision',
        related='template_id.company_id.currency_id.decimal_places',
        readonly=True,
        help="Precision for analytic amounts"
    )
