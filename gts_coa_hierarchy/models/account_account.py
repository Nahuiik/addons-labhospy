# -*- coding: utf-8 -*-
import logging
from operator import itemgetter

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError
from odoo.fields import Domain

_logger = logging.getLogger(__name__)


def _domain_restricts_by_account_id(domain):
    """True si el dominio restringe por id de cuenta (lectura puntual, ir.rule, many2one, etc.).

    Excluir cuentas tipo 'view' del _search rompe la comprobación de ir.rule multiempresa y la
    lectura de registros referenciados (p. ej. padres jerárquicos): el dominio incluye ('id', 'in',
    [...]) pero el filtro account_type != view vacía el resultado y el acceso 'read' falla.
    """
    if not domain:
        return False
    for item in domain:
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            if item[0] == 'id' and item[1] in ('=', 'in', 'child_of'):
                return True
        elif isinstance(item, (list, tuple)) and item:
            if _domain_restricts_by_account_id(item):
                return True
    return False


class AccountAccount(models.Model):
    _inherit = 'account.account'

    def init(self):
        """Initialize parent_path for existing records"""
        super().init()
        if self._parent_store:
            self._parent_store_compute()

    def check_cycle(self):
        """ climbs the ``self._table.parent_id`` chains for 100 levels or
        until it can't find any more parent(s)

        Returns true if it runs out of parents (no cycle), false if
        it can recurse 100 times without ending all chains
        """
        ids = self.ids
        cr = self.env.cr
        level = 100
        while len(ids):
            cr.execute('SELECT DISTINCT parent_id ' \
                       'FROM ' + self._table + ' ' \
                                               'WHERE id IN %s ' \
                                               'AND parent_id IS NOT NULL', (tuple(ids),))
            ids = list(map(itemgetter(0), cr.fetchall()))
            if not level:
                return False
            level -= 1
        return True

    @api.depends('parent_id', 'parent_path')
    def _get_level(self):
        """Compute account level based on hierarchy depth"""
        for account in self:
            if account.parent_path:
                account.level = account.parent_path.count('/') - 1
            elif account.parent_id:
                level = 0
                parent = account.parent_id
                visited = set()
                while parent and parent.id not in visited:
                    visited.add(parent.id)
                    level += 1
                    parent = parent.parent_id
                account.level = level
            else:
                account.level = 0

    def _get_children_and_consol(self):
        ids = [val.id for val in self]
        return self.search([('parent_id', 'child_of', ids)])

    @api.depends('child_parent_ids')
    def _get_child_ids(self):
        for record in self:
            if record.child_parent_ids:
                record.child_id = record.child_parent_ids
            else:
                record.child_id = self.env['account.account']

    @api.depends_context(
        'date_from', 'date_to', 'state', 'company_id', 'allowed_company_ids',
        'strict_range', 'initial_bal', 'aged_balance', 'show_initial_balance',
        'journal_ids', 'reconcile_date', 'account_tag_ids', 'analytic_tag_ids',
        'analytic_account_ids', 'partner_ids', 'partner_categories',
    )
    def _compute_balance_fields(self):
        """ compute the balance, debit and/or credit for the provided
        account ids
        """
        field_names = ['debit', 'credit', 'balance', 'opening_balance', 'closing_balance']
        children_and_consolidated = self._get_children_and_consol()
        accounts = {}
        opening_dict = {}
        consol_dict = {}

        if children_and_consolidated:
            ml_model = self.env['account.move.line']
            context = dict(self.env.context)
            domain = ml_model._build_coa_domain([
                ('account_id', 'in', children_and_consolidated.ids),
            ])

            debit_results = {
                account.id: debit_sum
                for account, debit_sum in ml_model._read_group(
                    domain, ['account_id'], ['debit:sum']
                )
            }
            credit_results = {
                account.id: credit_sum
                for account, credit_sum in ml_model._read_group(
                    domain, ['account_id'], ['credit:sum']
                )
            }

            for account_id in children_and_consolidated.ids:
                debit = debit_results.get(account_id, 0.0) or 0.0
                credit = credit_results.get(account_id, 0.0) or 0.0
                balance = debit - credit
                accounts[account_id] = {
                    'id': account_id,
                    'debit': debit,
                    'credit': credit,
                    'balance': balance,
                }

            if self.env.context.get('date_from'):
                opening_domain = [('account_id', 'in', children_and_consolidated.ids)]
                opening_domain.append(('date', '<', self.env.context.get('date_from')))
                opening_domain.append(('parent_state', '!=', 'cancel'))
                opening_domain.append(('display_type', 'not in', ('line_section', 'line_note', 'line_subsection')))
                if context.get('company_id'):
                    opening_domain.append(('company_id', '=', context['company_id']))
                elif context.get('allowed_company_ids'):
                    allowed_companies = context['allowed_company_ids']
                    if hasattr(allowed_companies, 'ids'):
                        allowed_companies = allowed_companies.ids
                    opening_domain.append(('company_id', 'in', allowed_companies))
                else:
                    opening_domain.append(('company_id', '=', self.env.company.id))

                opening_debit_results = {
                    account.id: debit_sum
                    for account, debit_sum in ml_model._read_group(
                        opening_domain, ['account_id'], ['debit:sum']
                    )
                }
                opening_credit_results = {
                    account.id: credit_sum
                    for account, credit_sum in ml_model._read_group(
                        opening_domain, ['account_id'], ['credit:sum']
                    )
                }

                for account_id in children_and_consolidated.ids:
                    opening_debit = opening_debit_results.get(account_id, 0.0) or 0.0
                    opening_credit = opening_credit_results.get(account_id, 0.0) or 0.0
                    opening_dict[account_id] = opening_debit - opening_credit

            if opening_dict:
                for akey in opening_dict.keys():
                    if accounts.get(akey, False):
                        accounts[akey].update({'opening_balance': opening_dict.get(akey, 0.0)})
                    else:
                        accounts[akey] = {
                            'debit': 0.0,
                            'credit': 0.0,
                            'id': akey,
                            'opening_balance': opening_dict.get(akey, 0.0)
                        }

            children_and_consolidated_records = children_and_consolidated
            sorted_accounts = sorted(
                children_and_consolidated_records,
                key=lambda a: (a.level if hasattr(a, 'level') and a.level is not False else 0, a.id),
                reverse=True
            )
            sums = {}

            for current in sorted_accounts:
                for fn in field_names:
                    sums.setdefault(current.id, {})[fn] = accounts.get(current.id, {}).get(fn, 0.0)

                direct_children = current.child_parent_ids

                if current.account_type == 'view' and direct_children:
                    consol_dict[current.id] = direct_children

                for fn in field_names:
                    for child in direct_children:
                        if child.id not in sums:
                            sums.setdefault(child.id, {})[fn] = accounts.get(child.id, {}).get(fn, 0.0)
                        if child.id in sums and fn not in sums[child.id]:
                            sums.setdefault(child.id, {})[fn] = accounts.get(child.id, {}).get(fn, 0.0)

                        child_currency = child.company_currency_id
                        current_currency = current.company_currency_id

                        if child_currency.id == current_currency.id:
                            sums[current.id][fn] += sums[child.id][fn]
                        else:
                            converted_amount = child_currency._convert(
                                sums[child.id][fn],
                                current_currency,
                                child.company_id,
                                fields.Date.context_today(self)
                            )
                            sums[current.id][fn] += converted_amount

            if consol_dict:
                for key, value in consol_dict.items():
                    closing_balance = credit = balance = opening_balance = debit = 0
                    for vl in value:
                        closing_balance += sums.get(vl.id, {}).get('closing_balance', 0)
                        credit += sums.get(vl.id, {}).get('credit', 0)
                        debit += sums.get(vl.id, {}).get('debit', 0)
                        balance += sums.get(vl.id, {}).get('balance', 0)
                        opening_balance += sums.get(vl.id, {}).get('opening_balance', 0)
                    sums[key] = {
                        'closing_balance': closing_balance,
                        'credit': credit,
                        'balance': balance,
                        'opening_balance': opening_balance,
                        'debit': debit
                    }

            show_ini = self.env.context.get('show_initial_balance')
            for acc in self:
                res = sums.get(acc.id, {})
                acc.debit = res.get('debit', 0.0)
                acc.credit = res.get('credit', 0.0)
                acc.balance = res.get('balance', 0.0)
                opening_val = res.get('opening_balance', 0.0)
                acc.opening_balance = opening_val
                acc.closing_balance = opening_val + res.get('balance', 0.0)
                acc.initial_balance = opening_val if show_ini else 0.0
        else:
            for acc in self:
                acc.debit = 0.0
                acc.credit = 0.0
                acc.balance = 0.0
                acc.opening_balance = 0.0
                acc.closing_balance = 0.0
                acc.initial_balance = 0.0

    account_type = fields.Selection(
        selection_add=[("view", "View")],
        ondelete={"view": "cascade"},
    )

    @api.depends('account_type')
    def _compute_internal_group(self):
        """Override to handle 'view' account_type"""
        for account in self:
            if account.account_type == "view":
                account.internal_group = 'off'
            else:
                account.internal_group = account._get_internal_group(account.account_type) if account.account_type else False

    type = fields.Selection([
        ('view', 'View'),
        ('other', 'Regular'),
        ('receivable', 'Receivable'),
        ('payable', 'Payable'),
        ('liquidity', 'Liquidity'),
        ('consolidation', 'Consolidation'),
        ('closed', 'Closed'),
        ('bank', 'Bank')
    ], string='Account Type Hie.', help="The 'Internal Type' is used for features available on " \
                            "different types of accounts: view can not have journal items, consolidation are accounts that " \
                            "can have children accounts for multi-company consolidations, payable/receivable are for " \
                            "partners accounts (for debit/credit computations), closed for depreciated accounts.")

    @api.depends('code', 'type')
    def _compute_account_type(self):
        """Evita account_type NULL: el core solo infiere por código; sin código o con padre NULL puede quedar vacío."""
        super()._compute_account_type()
        for account in self:
            if account.account_type:
                continue
            if account.type == 'view':
                account.account_type = 'view'
            else:
                account.account_type = 'asset_current'

    parent_id = fields.Many2one('account.account', string='Parent', domain=[('account_type', '=', 'view')], ondelete='set null', index=True)
    parent_path = fields.Char(index=True)
    level = fields.Integer(string='Account Level', compute='_get_level', store=True)
    child_parent_ids = fields.One2many('account.account', 'parent_id', string='Children')

    _parent_name = "parent_id"
    _parent_store = True
    _parent_order = 'code, name'
    child_id = fields.Many2many(
        "account.account",
        relation="account_account_child_rel",
        column1="parent_id",
        column2="child_id",
        compute='_get_child_ids',
        string="Child Accounts",
        store=False
    )
    balance = fields.Float(string="Hierarchy Balance", compute='_compute_balance_fields')
    credit = fields.Float(compute='_compute_balance_fields', string='Hierarchy Credit')
    debit = fields.Float(compute='_compute_balance_fields', string='Hierarchy Debit')
    closing_balance = fields.Float(string="Closing Balance", compute='_compute_balance_fields')
    opening_balance = fields.Float(string="Opening Balance", compute='_compute_balance_fields')
    initial_balance = fields.Float(
        string='Hierarchy Initial Balance',
        compute='_compute_balance_fields',
        help='Saldo inicial del periodo cuando el informe de plan solicita esa columna.',
    )

    @api.constrains('parent_id')
    def _check_recursion(self):
        if not self.check_cycle():
            raise ValidationError(_('Error!\nYou cannot create recursive accounts.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'account_type' in vals and not vals['account_type']:
                vals.pop('account_type', None)
            if not vals.get('account_type'):
                if not vals.get('code') and 'prefix' not in vals and not vals.get('code_mapping_ids'):
                    if vals.get('name'):
                        vals['account_type'] = 'asset_current'
        records = super().create(vals_list)
        missing = records.filtered(lambda r: not r.account_type)
        if missing:
            missing._compute_account_type()
            still = missing.filtered(lambda r: not r.account_type)
            if still:
                _logger.warning(
                    'gts_coa_hierarchy: account_type vacío tras create; usando asset_current para: %s',
                    still.mapped('code'),
                )
                still.write({'account_type': 'asset_current'})
        return records

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        extra_domain = list(domain or [])
        if not self.env.context.get('show_view_type'):
            extra_domain = extra_domain + [('account_type', '!=', 'view')]
        name_domain = []
        if name:
            name_domain = ['|', ('code', '=ilike', name + '%'), ('name', operator, name)]
            if operator in Domain.NEGATIVE_OPERATORS:
                name_domain = ['&', '!'] + name_domain[1:]
        if limit == 8:
            limit = 15
        if name_domain:
            full_domain = Domain.AND([name_domain, extra_domain or Domain.TRUE])
        else:
            full_domain = extra_domain or Domain.TRUE
        accounts = self.search(full_domain, limit=limit)
        return [(account.id, account.display_name or account.name) for account in accounts]

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """override search_read to not show view type account on account selection"""
        if not self.env.context.get('show_view_type'):
            if not domain:
                domain = []
            domain = Domain.AND([domain, [('account_type', '!=', 'view')]])
        return super(AccountAccount, self).search_read(
            domain=domain, fields=fields, offset=offset, limit=limit, order=order,
        )

    def write(self, vals):
        """Override write to recalculate levels of descendants when parent_id changes"""
        vals = dict(vals)
        if 'account_type' in vals and not vals['account_type']:
            vals.pop('account_type', None)
        result = super(AccountAccount, self).write(vals)
        if 'parent_id' in vals:
            for account in self:
                descendants = self.search([('id', 'child_of', account.id)])
                if descendants:
                    descendants._get_level()
        return result

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        """Override search to include parent accounts when needed"""
        context = dict(self.env.context)
        domain = list(domain or [])
        if (
            not context.get('show_view_type')
            and not context.get('show_parent_account')
            and not context.get('chart_template_load')
            and not context.get('hn_sync_account_codes')
            and not _domain_restricts_by_account_id(domain)
        ):
            domain.append(('account_type', '!=', 'view'))
        return super(AccountAccount, self)._search(
            domain, offset=offset, limit=limit, order=order, **kwargs
        )
