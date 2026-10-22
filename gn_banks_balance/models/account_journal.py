# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    gn_include_in_balance_dashboard = fields.Boolean(
        string='Mostrar en Balances',
        default=False,
        help=(
            'Si está marcado, el diario aparece en el menú Bancos › Balances '
            'con el saldo de su cuenta de liquidez.'
        ),
    )
    gn_balance_dashboard_balance = fields.Float(
        string='Saldo',
        compute='_compute_gn_balance_dashboard_balance',
        digits=(16, 2),
        help='Saldo liquidación del diario (movimientos publicados no cancelados).',
    )
    # Misma métrica que Balance en account.account (`current_balance` es Float suma apuntes publicados).
    gn_default_account_balance = fields.Float(
        string='Saldo de la cuenta contable',
        related='default_account_id.current_balance',
        digits=(16, 2),
        readonly=True,
    )

    @api.depends('default_account_id', 'currency_id', 'company_id')
    def _compute_gn_balance_dashboard_balance(self):
        # No usar `store=True`: debe recalcularse al refrescar por nuevos movimientos.
        eligible_types = self.env['banks.weekly.balance.common']._BALANCE_JOURNAL_TYPES
        for journal in self:
            journal.gn_balance_dashboard_balance = 0.0
            if journal.type not in eligible_types or not journal.default_account_id:
                continue
            balance, __ = journal._get_journal_bank_account_balance(
                domain=[('parent_state', '=', 'posted')]
            )
            journal.gn_balance_dashboard_balance = float(balance or 0.0)

    def action_open_weekly_balance_dashboard(self):
        """Abrir dashboard semanal con los diarios seleccionados (o todos en Balances)."""
        if self:
            eligible_types = self.env[
                'banks.weekly.balance.common'
            ]._BALANCE_JOURNAL_TYPES
            journals = self.filtered(
                lambda j: j.type in eligible_types and j.gn_include_in_balance_dashboard
            )
        else:
            journals = self.env['banks.weekly.balance.common'].search_balance_journals(
                self.env.company.id,
            )
        if not journals:
            raise UserError(_(
                'No hay diarios de banco marcados para Balances con los '
                'filtros seleccionados.'
            ))
        companies = journals.mapped('company_id')
        if len(companies) > 1:
            raise UserError(_(
                'Seleccione diarios de una sola compañía para el análisis semanal.'
            ))
        return {
            'type': 'ir.actions.client',
            'tag': 'gn_banks_balance_weekly_dashboard',
            'name': _('Balance semanal por banco'),
            'context': {
                'dashboard_journal_ids': journals.ids,
                'dashboard_company_id': companies.id,
            },
        }
