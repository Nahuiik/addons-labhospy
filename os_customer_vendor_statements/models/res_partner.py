from datetime import date, timedelta
from odoo import api, fields, models, _

try:
    import base64
except ImportError:
    base64 = None


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Cron functions

    def _ir_cron_monthly_customer_statements(self):
        company_id = self.env.user.company_id
        if company_id.monthly_statement_auto_upt and company_id.enable_customer_statements:
            for partner in self.env['res.partner'].search([('exclude_auto_sent', '=', False)]):
                partner._compute_weekly_monthly_due_and_overdue()
                if partner.email and partner.monthly_customer_amount_due != 0.00:
                    template_selected = company_id.mail_template_monthly_id
                    template = template_selected if template_selected else self.env.ref(
                        'os_customer_vendor_statements.mail_template_monthly_customer_statements')
                    report_data = self.env.ref(
                        'os_customer_vendor_statements.report_monthly_customer_statements').report_action(
                        self, data={'partner_id': partner})
                    template.report_template_ids = \
                        [self.env['ir.actions.report'].search([('report_name', '=', report_data['report_name'])]).id]
                    customer_list = [val for val in partner.child_ids if val.email and val.type == 'invoice']
                    if partner.email and not customer_list:
                        customer_list = [partner]
                    for customer in customer_list:
                        template.send_mail(customer.id, force_send=True)
                        msg = _(
                            "Monthly Customer's Statement sent to %s - %s" % (customer.name, customer.email))
                        customer.message_post(body=msg)

    def _ir_cron_weekly_customer_statements(self):
        company_id = self.env.user.company_id
        if company_id.sent_day_weekly and company_id.enable_customer_statements and company_id.weekly_statement_auto_upt:
            for partner in self.env['res.partner'].search([('exclude_auto_sent', '=', False)]):
                partner._compute_weekly_monthly_due_and_overdue()
                if partner.email and partner.weekly_customer_amount_due != 0.00:
                    template_selected = company_id.mail_template_weekly_id
                    template = template_selected if template_selected else self.env.ref(
                        'os_customer_vendor_statements.mail_template_weekly_customer_statements')
                    report_data = self.env.ref(
                        'os_customer_vendor_statements.report_weekly_customer_statements').report_action(
                        self, data={'partner_id': partner})
                    template.report_template_ids = \
                        [self.env['ir.actions.report'].search([('report_name', '=', report_data['report_name'])]).id]
                    customer_list = [val for val in partner.child_ids if val.email and val.type == 'invoice']
                    if partner.email and not customer_list:
                        customer_list = [partner]
                    for customer in customer_list:
                        template.send_mail(customer.id, force_send=True)
                        msg = _(
                            "Weekly Customer's Statement sent to %s - %s" % (customer.name, customer.email))
                        customer.message_post(body=msg)

    def _ir_cron_customer_overdue_statements(self):
        company_id = self.env.user.company_id
        if company_id.enable_overdue_sent:
            for partner in self.env['res.partner'].search([('exclude_auto_sent', '=', False)]):
                partner._compute_customer_amount_overdue_and_due()
                if partner.email and partner.customer_amount_overdue != 0.00:
                    template_selected = company_id.overdue_temp_id
                    template = template_selected if template_selected else self.env.ref(
                        'os_customer_vendor_statements.mail_template_customer_overdue_statements')
                    report_data = self.env.ref(
                        'os_customer_vendor_statements.report_customer_overdue_statements').report_action(
                        self, data={'partner_id': partner})
                    template.report_template_ids = \
                        [self.env['ir.actions.report'].search([('report_name', '=', report_data['report_name'])]).id]
                    customer_list = [val for val in partner.child_ids if val.email and val.type == 'invoice']
                    if partner.email and not customer_list:
                        customer_list = [partner]
                    for customer in customer_list:
                        template.send_mail(customer.id, force_send=True)
                        msg = _(
                            "Customer's Overdue Statement sent to %s - %s" % (customer.name, customer.email))
                        customer.message_post(body=msg)

    # Basic methods

    def _compute_customer_amount_overdue_and_due(self):
        date_today = fields.Date.today()
        for customer in self:
            due_amount = amount_overdue = 0.0
            search_record = self.env['account.move'].search_read(
                [('id', 'in', customer.customer_amount_ids.ids), ('company_id', '=', customer.env.company.id)],
                fields=['invoice_date_due', 'remaining_due_amount', 'date'])
            for move in search_record:
                date_maturity = move['invoice_date_due'] or move['date']
                due_amount += move['remaining_due_amount']
                if date_maturity and date_maturity <= date_today:
                    amount_overdue += move['remaining_due_amount']
            customer.customer_amount_due = due_amount
            customer.customer_amount_overdue = amount_overdue

    def _compute_vendor_amount_overdue_and_due(self):
        date_today = fields.Date.today()
        for customer in self:
            due_amount = amount_overdue = 0.0
            search_record = self.env['account.move'].search_read(
                [('id', 'in', customer.vendor_amount_ids.ids), ('company_id', '=', customer.env.company.id)],
                fields=['invoice_date_due', 'remaining_due_amount', 'date'])
            for move in search_record:
                date_maturity = move['invoice_date_due'] or move['date']
                due_amount += move['remaining_due_amount']
                if date_maturity and date_maturity <= date_today:
                    amount_overdue += move['remaining_due_amount']
            customer.vendor_amount_due = due_amount
            customer.vendor_amount_overdue = amount_overdue

    def _compute_common_aged_analysis(self):
        """Compute the Aged Analysis"""
        for customer in self:
            customer.first_thirty = customer.thirty_sixty = customer.sixty_ninety = customer.ninety_plus = customer.analysis_total = 0
            domain = [('partner_id', '=', customer.id), ('state', 'in', ['posted'])]
            data_dict = [vals for data in self.env['account.move'].search(domain) for vals in data.line_ids if
                         vals.account_id.account_type == 'asset_receivable']
            for move in data_dict:
                if move.date_maturity:
                    date_diff = customer.date_today - move.date_maturity
                else:
                    date_diff = customer.date_today - customer.date_today
                if 0 <= date_diff.days <= 30:
                    customer.first_thirty = customer.first_thirty + move.amount_residual
                elif 30 < date_diff.days <= 60:
                    customer.thirty_sixty = customer.thirty_sixty + move.amount_residual
                elif 60 < date_diff.days <= 90:
                    customer.sixty_ninety = customer.sixty_ninety + move.amount_residual
                else:
                    if date_diff.days > 90:
                        customer.ninety_plus = customer.ninety_plus + move.amount_residual
                if customer.first_thirty or customer.thirty_sixty or customer.sixty_ninety or \
                        customer.ninety_plus:
                    customer.analysis_total = customer.first_thirty + customer.thirty_sixty + \
                                              customer.sixty_ninety + customer.ninety_plus
            return

    @api.depends('customer_filter_line_ids', 'vendor_filter_line_ids')
    def _compute_filtered_customer_vendor_due_and_overdue(self):
        date_today = fields.Date.today()
        for partner in self:
            partner.customer_filter_amount_due = 0.0
            partner.customer_filter_amount_overdue = 0.0
            partner.vendor_filter_amount_due = 0.0
            partner.vendor_filter_amount_overdue = 0.0
            if partner.customer_filter_line_ids:
                partner.customer_filter_amount_due = sum(
                    [x.remaining_due_amount for x in partner.customer_filter_line_ids if x.due_invoice_date])
                partner.customer_filter_amount_overdue = sum(
                    [x.remaining_due_amount for x in partner.customer_filter_line_ids if
                     x.due_invoice_date and x.due_invoice_date <= date_today])
            if partner.vendor_filter_line_ids:
                partner.vendor_filter_amount_due = sum(
                    [x.remaining_due_amount for x in partner.vendor_filter_line_ids if x.due_invoice_date])
                partner.vendor_filter_amount_overdue = sum(
                    [x.remaining_due_amount for x in partner.vendor_filter_line_ids if
                     x.due_invoice_date and x.due_invoice_date <= date_today])

    @api.depends('weekly_customer_amount_ids', 'monthly_customer_amount_ids')
    def _compute_weekly_monthly_due_and_overdue(self):
        date_today = fields.Date.today()
        for partner in self:
            partner.weekly_customer_amount_due = 0.0
            partner.weekly_customer_amount_overdue = 0.0
            partner.monthly_customer_amount_due = 0.0
            partner.monthly_customer_amount_overdue = 0.0
            if partner.weekly_customer_amount_ids:
                partner.weekly_customer_amount_due = sum(
                    [x.remaining_due_amount for x in partner.weekly_customer_amount_ids if x.invoice_date_due])
                partner.weekly_customer_amount_overdue = sum(
                    [x.remaining_due_amount for x in partner.weekly_customer_amount_ids if
                     x.invoice_date_due and x.invoice_date_due <= date_today])
            if partner.monthly_customer_amount_ids:
                partner.monthly_customer_amount_due = sum(
                    [x.remaining_due_amount for x in partner.monthly_customer_amount_ids if x.invoice_date_due])
                partner.monthly_customer_amount_overdue = sum(
                    [x.remaining_due_amount for x in partner.monthly_customer_amount_ids if
                     x.invoice_date_due and x.invoice_date_due <= date_today])

    @api.depends('custom_customer_amount_ids')
    def _compute_custom_customer_due_and_overdue(self):
        date_today = fields.Date.today()
        for partner in self:
            partner.custom_customer_amount_due = 0.0
            partner.custom_customer_amount_overdue = 0.0
            if partner.custom_customer_amount_ids:
                partner.custom_customer_amount_due = sum(
                    [x.remaining_due_amount for x in partner.custom_customer_amount_ids if x.invoice_date_due])
                partner.custom_customer_amount_overdue = sum(
                    [x.remaining_due_amount for x in partner.custom_customer_amount_ids if
                     x.invoice_date_due and x.invoice_date_due <= date_today])

    # button functions

    def action_sent_all_mail_statements(self):
        for partner in self:
            if partner.email:
                if not self._context.get('customer_filter'):
                    report_data = partner.action_customer_vendor_statements() if self._context.get(
                        'due') else partner.action_customer_overdue_statement()
                    report_name = 'os_customer_vendor_statements.mail_template_customer_statements' if self._context.get(
                        'due') else 'os_customer_vendor_statements.mail_template_customer_overdue_statements'
                    template = self.env.ref(report_name)
                else:
                    report_data = partner.action_filtered_customer_vendor_statements()
                    template = self.env.ref('os_customer_vendor_statements.mail_template_filtered_customer_statements')
                template.report_template_ids = \
                    [self.env['ir.actions.report'].search([('report_name', '=', report_data['report_name'])]).id]
                customer_list = [val for val in partner.child_ids if val.email and val.type == 'invoice']
                if partner.email and not customer_list:
                    customer_list = [partner]
                for customer in customer_list:
                    template.send_mail(customer.id, force_send=True)
                    if not self._context.get('customer_filter'):
                        msg = _("Customer's Statement sent to %s - %s" % (
                            customer.name, customer.email)) if self._context.get(
                            'due') else _(
                            "Customer's Overdue Statement sent to %s - %s" % (customer.name, customer.email))
                    else:
                        msg = _(
                            " Customer's Filtered Statement sent to %s - %s" % (customer.name, customer.email))
                    customer.message_post(body=msg)

    def action_customer_vendor_statements(self):
        self.ensure_one()
        report_name = 'os_customer_vendor_statements.report_customer_statements' if self._context.get(
            'customer') else 'os_customer_vendor_statements.report_vendor_statements'
        return self.env.ref(report_name).report_action(self)

    def action_customer_overdue_statement(self):
        self.ensure_one()
        return self.env.ref('os_customer_vendor_statements.report_customer_overdue_statements').report_action(self)

    def action_filtered_customer_vendor_statements(self):
        self.ensure_one()
        report_name = 'os_customer_vendor_statements.report_filtered_customer_statements' if self._context.get(
            'customer') else 'os_customer_vendor_statements.report_filtered_vendor_statements'
        return self.env.ref(report_name).report_action(self)

    def action_open_filter_customer_vendor_statement_form(self):
        self.ensure_one()
        view_id = 'os_customer_vendor_statements.view_customer_filtered_statements' if self._context.get(
            'customer') else 'os_customer_vendor_statements.view_vendor_filtered_statements'
        view = self.env.ref(view_id)
        name = '%s Filter Statement View' % 'Customer' if self._context.get('customer') else 'Vendor'
        return {
            'name': _(name),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'res.partner',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id': self.id,
        }

    def action_fetch_customer_vendor_filtered_statements(self):
        for partner in self:
            domain = [('partner_id', '=', partner.id), ('move_type', 'in',
                                                        ['in_invoice', 'in_refund']),
                      ('state', 'in', ['posted']), \
                      ('invoice_date', '<',
                       partner.customer_filter_date_from if self._context.get(
                           'customer') else partner.vendor_filter_date_from),
                      (
                          'date', '<',
                          partner.customer_filter_date_from if self._context.get(
                              'customer') else partner.vendor_filter_date_from),
                      ('payment_state', 'not in', ['paid'])]
            if self._context.get('customer') and partner.customer_filter_date_from:
                amount_residual_total = sum([x['amount_residual'] for x in
                                             self.env['account.move'].search_read(domain, fields=['amount_residual'])])
                pay_amount_total = sum(
                    [x['amount'] for x in self.env['account.payment'].search_read(domain, fields=['amount'])])
                customer_init_balance = (
                        amount_residual_total - pay_amount_total) if amount_residual_total and pay_amount_total else 0.0
                if customer_init_balance:
                    partner.write({'customer_init_balance': customer_init_balance})
            filter_history = self.env['filtered.customer.statements'].search([('partner_id', '=', partner.id)])
            if filter_history:
                filter_history.unlink()
            if self._context.get('customer'):
                domain = [('move_type', 'in', ['out_invoice', 'out_refund']), ('state', 'in', ['posted']),
                          ('partner_id', '=', partner.id),
                          ('payment_state', 'not in', ['paid']),
                          ('invoice_date', '>=',
                           partner.customer_filter_date_from) if partner.customer_filter_date_from else None,
                          ('invoice_date', '<=',
                           partner.customer_filter_date_to) if partner.customer_filter_date_to else None]
            elif self._context.get('vendor'):
                domain = [('move_type', 'in', ['in_invoice', 'in_refund']), ('state', 'in', ['posted']),
                          ('payment_state', 'not in', ['paid']),
                          ('partner_id', '=', partner.id), ('invoice_date', '>=',
                                                            partner.vendor_filter_date_from) if partner.vendor_filter_date_from else None,
                          ('invoice_date', '<=',
                           partner.vendor_filter_date_to) if partner.vendor_filter_date_to else None]
            else:
                domain = None
            invoices = self.env['account.move'].search(domain)
            HistoryModel = 'filtered.customer.statements' if self._context.get(
                'customer') else 'filtered.vendor.statements'
            search_history = self.env[HistoryModel].search([('partner_id', '=', partner.id)])
            if search_history:
                search_history.unlink()
            if invoices:
                domain_filtered = [
                    dict(partner_id=invoice.partner_id.id or False,
                         due_invoice_date=invoice.invoice_date_due or None,
                         state=invoice.state or False,
                         invoice_date=invoice.invoice_date or None,
                         payment_state=invoice.payment_state or False,
                         remaining_due_amount=invoice.remaining_due_amount or 0.0,
                         amount_total=invoice.amount_total or 0.0,
                         transaction_ids=invoice.transaction_ids.ids or [],
                         move_type=invoice.move_type or False,
                         reference=invoice.name or '',
                         credit_amount=invoice.credit_amount or 0.0,
                         invoice_id=invoice.id) for
                    invoice in
                    invoices.sorted(key=lambda x: x.name)]
                if self._context.get('customer'):
                    for move in domain_filtered:
                        self.env['filtered.customer.statements'].create(move)
                if self._context.get('vendor'):
                    for move in domain_filtered:
                        self.env['filtered.vendor.statements'].create(move)
        view_id = 'os_customer_vendor_statements.view_customer_filtered_statements' if self._context.get(
            'customer') else 'os_customer_vendor_statements.view_vendor_filtered_statements'
        view = self.env.ref(view_id)
        name = '%s Filter Statement View' % 'Customer' if self._context.get('customer') else 'Vendor'
        return {
            'name': _(name),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'res.partner',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id': self.id,
        }

    def _sent_email_custom_customer_statements(self):
        for partner in self:
            if partner.email:
                template = self.env.ref('os_customer_vendor_statements.mail_template_custom_customer_statements')
                report_data = self.env.ref(
                    'os_customer_vendor_statements.report_custom_customer_statements').report_action(
                    self,
                    data={
                        'partner_id': partner})
                template.report_template_ids = \
                    [self.env['ir.actions.report'].search([('report_name', '=', report_data['report_name'])]).id]
                customer_list = [val for val in partner.child_ids if val.email and val.type == 'invoice']
                if partner.email and not customer_list:
                    customer_list = [partner]
                for customer in customer_list:
                    template.send_mail(customer.id, force_send=True)
                    msg = _(
                        " Customer's Custom Statement sent to %s - %s" % (customer.name, customer.email))
                    customer.message_post(body=msg)

    # Basic fields
    customer_amount_ids = fields.One2many('account.move', 'partner_id', 'Customer Balance Lines',
                                          domain=[('payment_state', 'not in', ['paid']), ('state', 'in', ['posted']),
                                                  ('move_type', 'in', ['out_refund', 'out_invoice'])])

    customer_amount_overdue = fields.Float(compute='_compute_customer_amount_overdue_and_due',
                                           string="Customer Total Overdue Amount", store=True, compute_sudo=False)
    customer_amount_due = fields.Float(compute='_compute_customer_amount_overdue_and_due', string="Customer Due Amount", store=True, compute_sudo=False)
    vendor_amount_ids = fields.One2many('account.move', 'partner_id', 'Vendor Amount Lines',
                                        domain=[('state', 'in', ['posted']),
                                                ('move_type', 'in', ['in_invoice', 'in_refund'])])
    vendor_amount_overdue = fields.Float(compute='_compute_vendor_amount_overdue_and_due',
                                         string="Vendor Total Overdue Amount", store=True, compute_sudo=False)
    vendor_amount_due = fields.Float(compute='_compute_vendor_amount_overdue_and_due', string="Vendor Due Amount", store=True, compute_sudo=False)
    date_today = fields.Date(default=fields.Date.today())
    # Aged Analysis
    first_thirty = fields.Float(string="Aged Analysis 0-30", compute="_compute_common_aged_analysis")
    thirty_sixty = fields.Float(string="Aged Analysis 30-60", compute="_compute_common_aged_analysis")
    sixty_ninety = fields.Float(string="Aged Analysis 60-90", compute="_compute_common_aged_analysis")
    ninety_plus = fields.Float(string="Aged Analysis 90+", compute="_compute_common_aged_analysis")
    analysis_total = fields.Float(string="Aged Analysis Total", compute="_compute_common_aged_analysis")

    # filter section
    customer_filter_date_from = fields.Date('Customer Filter From Date')
    customer_filter_date_to = fields.Date('Customer Filter To Date')
    customer_init_balance = fields.Float('Initial Balance')
    customer_filter_line_ids = fields.One2many('filtered.customer.statements', 'partner_id', 'Filter Customer Lines')
    customer_filter_amount_due = fields.Float(compute='_compute_filtered_customer_vendor_due_and_overdue',
                                              string="Customer Filtered Balance Due Amount", store=True, compute_sudo=False)
    customer_filter_amount_overdue = fields.Float(compute='_compute_filtered_customer_vendor_due_and_overdue',
                                                  string="Customer Filtered Total Overdue Amount", store=True, compute_sudo=False)
    vendor_filter_date_from = fields.Date('Vendor Filter From Date')
    vendor_filter_date_to = fields.Date('Vendor Filter To Date')
    vendor_init_balance = fields.Float('Vendor Initial Balance')
    vendor_filter_line_ids = fields.One2many('filtered.vendor.statements', 'partner_id', 'Filter Vendor Data Lines')
    vendor_filter_amount_due = fields.Float(compute='_compute_filtered_customer_vendor_due_and_overdue',
                                            string="Vendor Filtered Balance Due Amount", store=True, compute_sudo=False)
    vendor_filter_amount_overdue = fields.Float(
        compute='_compute_filtered_customer_vendor_due_and_overdue',
        string="Vendor Filtered Total Overdue Amount", store=True, compute_sudo=False)

    # monthly and weekly reports

    def _weekly_customer_amount_ids_domain(self):
        today = date.today()
        start_date = today + timedelta(-today.weekday(), weeks=-1)
        end_date = today + timedelta(-today.weekday() - 1)
        return [('move_type', 'in', ['out_invoice', 'out_refund']), ('state', 'in', ['posted']),
                ('invoice_date', '>=', str(start_date)),
                ('payment_state', 'not in', ['paid']), ('invoice_date', '<=', str(end_date))]

    def _monthly_customer_amount_ids_domain(self):
        end_date = date.today().replace(day=1) - timedelta(days=1)
        start_date = end_date.replace(day=1)
        return [('move_type', 'in', ['out_invoice', 'out_refund']), ('state', 'in', ['posted']),
                ('invoice_date', '>=', str(start_date)),
                ('payment_state', 'not in', ['paid']), ('invoice_date', '<=', str(end_date))]

    weekly_customer_amount_ids = fields.One2many('account.move', 'partner_id', 'Weekly Customer Balance Lines',
                                                 domain=_weekly_customer_amount_ids_domain, store=True)
    monthly_customer_amount_ids = fields.One2many('account.move', 'partner_id', 'Monthly Customer Balance Lines',
                                                  domain=_monthly_customer_amount_ids_domain, store=True)
    weekly_customer_amount_due = fields.Float(compute='_compute_weekly_monthly_due_and_overdue',
                                              string="Weekly Balance Due Amount", store=True, compute_sudo=False)
    weekly_customer_amount_overdue = fields.Float(compute='_compute_weekly_monthly_due_and_overdue',
                                                  string="Weekly Total Overdue Amount", store=True, compute_sudo=False)
    monthly_customer_amount_due = fields.Float(compute='_compute_weekly_monthly_due_and_overdue',
                                               string="Monthly Balance Due Amount", store=True, compute_sudo=False)
    monthly_customer_amount_overdue = fields.Float(compute='_compute_weekly_monthly_due_and_overdue',
                                                   string="Monthly Total Overdue Amount", store=True, compute_sudo=False)

    # custom fields

    def _compute_common_custom_aged_analysis(self):
        for customer in self:
            customer.c_first_thirty = customer.c_thirty_sixty = customer.c_sixty_ninety = customer.c_ninety_plus = customer.c_analysis_total = 0
            domain = [('partner_id', '=', customer.id), ('state', 'in', ['posted'])]
            data_dict = [vals for data in self.env['account.move'].search(domain) for vals in data.line_ids if
                         vals.date_maturity and vals.account_id.account_type == 'asset_receivable' and customer.c_date_from <= vals.date_maturity <= customer.c_date_to]
            for move in data_dict:
                if move.date_maturity:
                    date_diff = customer.date_today - move.date_maturity
                else:
                    date_diff = customer.date_today - customer.date_today
                if 0 <= date_diff.days <= 30:
                    customer.c_first_thirty = customer.c_first_thirty + move.amount_residual
                elif 30 < date_diff.days <= 60:
                    customer.c_thirty_sixty = customer.c_thirty_sixty + move.amount_residual
                elif 60 < date_diff.days <= 90:
                    customer.c_sixty_ninety = customer.c_sixty_ninety + move.amount_residual
                else:
                    if date_diff.days > 90:
                        customer.c_ninety_plus = customer.c_ninety_plus + move.amount_residual
                if customer.c_first_thirty or customer.c_thirty_sixty or customer.c_sixty_ninety or \
                        customer.c_ninety_plus:
                    customer.c_analysis_total = customer.c_first_thirty + customer.c_thirty_sixty + \
                                                customer.c_sixty_ninety + customer.c_ninety_plus
            return

    @api.depends('c_date_from', 'c_date_to')
    def _compute_custom_customer_amount_ids(self):
        for partner in self:
            domain = [('move_type', 'in', ['out_invoice', 'out_refund']), ('state', 'in', ['posted']),
                      ('payment_state', 'not in', ['paid']),
                      ('partner_id', '=', partner.id), ('invoice_date', '>=',
                                                        str(partner.c_date_from) if partner.c_date_from else None),
                      ('invoice_date', '<=', str(partner.c_date_to) if partner.c_date_to else None)]
            move_ids = self.env['account.move'].search(domain).ids
            partner.custom_customer_amount_ids = move_ids if move_ids else False

    custom_customer_amount_ids = fields.Many2many('account.move', string='Customer Custom Statements',
                                                  compute='_compute_custom_customer_amount_ids', store=True)
    custom_customer_amount_due = fields.Float(compute='_compute_custom_customer_due_and_overdue',
                                              string="Custom Balance Due Amount", store=True, compute_sudo=False)
    custom_customer_amount_overdue = fields.Float(compute='_compute_custom_customer_due_and_overdue',
                                                  string="Custom Total Overdue Amount", store=True, compute_sudo=False)
    custom_period = fields.Selection([
        ('30', 'Thirty Days '),
        ('60', 'Sixty Days'),
        ('90', 'Ninety Days'),
        ('3_month', 'Quarter'),
        ('custom', 'Custom Date Range'),
    ], string="Duration", required=True, default="30")
    c_date_from = fields.Date('Custom Analysis From Date')
    c_date_to = fields.Date('Custom Analysis To Date')
    c_first_thirty = fields.Float(string="Custom 0-30", compute="_compute_common_custom_aged_analysis")
    c_thirty_sixty = fields.Float(string="Custom 30-60", compute="_compute_common_custom_aged_analysis")
    c_sixty_ninety = fields.Float(string="Custom 60-90", compute="_compute_common_custom_aged_analysis")
    c_ninety_plus = fields.Float(string="Custom 90+", compute="_compute_common_custom_aged_analysis")
    c_analysis_total = fields.Float(string="Custom Total", compute="_compute_common_custom_aged_analysis")
    exclude_auto_sent = fields.Boolean('Exclude Auto Sent', default=False)
