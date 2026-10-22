from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'


    @api.model
    def _get_default_branch(self):
        return self.env.user.branch_id.id or False

    branch_id = fields.Many2one('res.branch', 'Branch', default=_get_default_branch)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('branch_id') and vals.get('move_id'):
                move = self.env['account.move'].browse(vals['move_id'])
                vals['branch_id'] = move.branch_id.id
        lines = super().create(vals_list)
        for line in lines:
            if line.move_id.branch_id and not line.branch_id:
                line.branch_id = line.move_id.branch_id.id
        return lines


    @api.model
    def _build_coa_domain(self, domain=None):
        ''' Inherited for adding branch condition in query '''
        domain = list(domain or [])
        if not isinstance(domain, (list, tuple)):
            domain = safe_eval(domain)
        context = dict(self.env.context)

        branch_field = 'branch_id'
        branch_filter = context.get('branch_ids')
        if branch_filter:
            if isinstance(branch_filter, (list, tuple, set)):
                domain.append((branch_field, 'in', list(branch_filter)))
            else:
                domain.append((branch_field, '=', branch_filter))

        date_field = 'date_maturity' if context.get('aged_balance') else 'date'
        if context.get('date_to'):
            domain.append((date_field, '<=', context['date_to']))
        if context.get('date_from'):
            if not context.get('strict_range'):
                domain += ['|', (date_field, '>=', context['date_from']),
                           ('account_id.user_type_id.include_initial_balance', '=', True)]
            elif context.get('initial_bal'):
                domain.append((date_field, '<', context['date_from']))
            else:
                domain.append((date_field, '>=', context['date_from']))

        if context.get('journal_ids'):
            journal_ids = context['journal_ids']
            if hasattr(journal_ids, 'ids'):
                journal_ids = journal_ids.ids
            domain.append(('journal_id', 'in', journal_ids))

        state = context.get('state')
        if state and state.lower() != 'all':
            domain.append(('move_id.state', '=', state))

        if context.get('company_id'):
            domain.append(('company_id', '=', context['company_id']))
        elif context.get('company_ids'):
            company_ids = context['company_ids']
            if hasattr(company_ids, 'ids'):
                company_ids = company_ids.ids
            domain.append(('company_id', 'in', company_ids))
        else:
            domain.append(('company_id', '=', self.env.company.id))

        if context.get('reconcile_date'):
            domain += ['|', ('reconciled', '=', False), '|',
                       ('matched_debit_ids.max_date', '>', context['reconcile_date']),
                       ('matched_credit_ids.max_date', '>', context['reconcile_date'])]

        if context.get('account_tag_ids'):
            tag_ids = context['account_tag_ids']
            if hasattr(tag_ids, 'ids'):
                tag_ids = tag_ids.ids
            domain.append(('account_id.tag_ids', 'in', tag_ids))

        if context.get('account_ids'):
            account_ids = context['account_ids']
            if hasattr(account_ids, 'ids'):
                account_ids = account_ids.ids
            domain.append(('account_id', 'in', account_ids))

        if context.get('analytic_tag_ids'):
            analytic_tags = context['analytic_tag_ids']
            if hasattr(analytic_tags, 'ids'):
                analytic_tags = analytic_tags.ids
            domain += ['|', ('analytic_account_id.tag_ids', 'in', analytic_tags),
                       ('analytic_tag_ids', 'in', analytic_tags)]

        if context.get('analytic_account_ids'):
            analytic_accounts = context['analytic_account_ids']
            if hasattr(analytic_accounts, 'ids'):
                analytic_accounts = analytic_accounts.ids
            domain.append(('analytic_account_id', 'in', analytic_accounts))

        return super()._build_coa_domain(domain)
