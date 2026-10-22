# -*- coding: utf-8 -*-
"""Informe de conciliación bancaria: saldo en libros vs movimientos de extracto."""

from odoo import api, fields, models, _
from odoo.tools.misc import formatLang


class BankReconciliationReport(models.Model):
    _name = 'bank.reconciliation.report'
    _description = 'Bank Reconciliation Report'

    @api.model
    def get_data_bank_reconciliation(self):
        ctx = self.env.context
        date_to = ctx.get('date_to') or fields.Date.today()
        if isinstance(date_to, str):
            date_to = fields.Date.from_string(date_to)
        journal_ids = ctx.get('journal_ids') or []
        target_move = ctx.get('target_move') or 'posted'

        domain = [('type', 'in', ('bank', 'cash'))]
        if journal_ids:
            domain.append(('id', 'in', journal_ids))
        journals = self.env['account.journal'].search(domain, order='name')

        company_currency = self.env.company.currency_id
        lines_out = []
        has_draft_warning = False
        if target_move == 'posted' and journals:
            has_draft_warning = bool(self.env['account.move.line'].search([
                ('parent_state', '=', 'draft'),
                ('journal_id', 'in', journals.ids),
                ('date', '<=', date_to),
            ], limit=1))

        for journal in journals:
            acc = journal.default_account_id
            if not acc:
                continue
            aml_dom = [
                ('account_id', '=', acc.id),
                ('date', '<=', date_to),
                ('journal_id', '=', journal.id),
            ]
            if target_move == 'posted':
                aml_dom.append(('parent_state', '=', 'posted'))
            else:
                aml_dom.append(('parent_state', 'in', ('draft', 'posted')))

            amls = self.env['account.move.line'].search(aml_dom)
            book_balance = sum(amls.mapped('balance'))

            st_dom = [
                ('journal_id', '=', journal.id),
                ('date', '<=', date_to),
            ]
            if 'account.bank.statement.line' in self.env:
                stmt_lines = self.env['account.bank.statement.line'].search(st_dom)
                statement_total = sum(sl.amount for sl in stmt_lines)
            else:
                statement_total = 0.0

            diff = book_balance - statement_total
            lines_out.append({
                'journal_id': journal.id,
                'journal_code': journal.code or '',
                'journal_name': journal.name or '',
                'account_code': acc.code or '',
                'book_balance': book_balance,
                'statement_balance': statement_total,
                'difference': diff,
                'book_balance_fmt': formatLang(self.env, book_balance, currency_obj=company_currency),
                'statement_balance_fmt': formatLang(self.env, statement_total, currency_obj=company_currency),
                'difference_fmt': formatLang(self.env, diff, currency_obj=company_currency),
                'difference_negative': diff < 0,
            })

        currency_data = {
            'id': company_currency.id,
            'symbol': company_currency.symbol,
            'position': company_currency.position,
            'decimal_places': company_currency.decimal_places,
        }
        return {
            'date_to': fields.Date.to_string(date_to),
            'company': self.env.company.name,
            'currency_data': currency_data,
            'lines': lines_out,
            'has_draft_warning': has_draft_warning,
        }

    @api.model
    def action_open_journal_items(self, journal_id, date_to, target_move):
        journal = self.env['account.journal'].browse(int(journal_id))
        if not journal.exists() or not journal.default_account_id:
            return False
        domain = [
            ('journal_id', '=', journal.id),
            ('account_id', '=', journal.default_account_id.id),
            ('date', '<=', date_to),
        ]
        if target_move == 'posted':
            domain.append(('parent_state', '=', 'posted'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Apuntes: %(j)s', j=journal.display_name),
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {'search_default_posted': target_move == 'posted'},
        }
