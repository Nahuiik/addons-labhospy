# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class BanksWeeklyBalanceDashboard(models.AbstractModel):
    """API RPC para el dashboard OWL de balance semanal bancario."""

    _name = 'banks.weekly.balance.dashboard'
    _description = 'Dashboard interactivo balance semanal bancos (OWL)'

    @api.model
    def get_filter_options(self, company_id=None):
        """Opciones de filtros para la UI (compañía, meses, diarios)."""
        company = self.env['res.company'].browse(
            company_id or self.env.company.id
        )
        if not company.exists():
            raise UserError(_('Compañía no válida.'))
        company.check_access('read')

        common = self.env['banks.weekly.balance.common']
        journals = common.search_balance_journals(company.id)

        companies = self.env.companies
        today = fields.Date.context_today(self)
        # Reuse the single source of truth for month names (also used by the
        # report/QWeb layer) instead of re-listing them here.
        months = [
            {'id': str(i), 'name': common._translated_month_name(i)}
            for i in range(1, 13)
        ]
        return {
            'company_id': company.id,
            'companies': [
                {'id': c.id, 'name': c.name} for c in companies
            ],
            'multi_company': len(companies) > 1,
            'can_view_financial_health': self._can_view_financial_health(),
            'currency_id': company.currency_id.id,
            'currency_name': company.currency_id.name,
            'year': today.year,
            'month': str(today.month),
            'months': months,
            'group_by_options': [
                {'id': 'week', 'name': _('Por semana')},
                {'id': 'fortnight', 'name': _('Por quincena')},
                {'id': 'month', 'name': _('Por mes')},
            ],
            'journals': [
                {
                    'id': j.id,
                    'name': j.name,
                    'has_liquidity_account': bool(j.default_account_id),
                }
                for j in journals
            ],
        }

    @api.model
    def _parse_filters(self, filters):
        company_id = filters.get('company_id') or self.env.company.id
        company = self.env['res.company'].browse(company_id)
        if not company.exists():
            raise UserError(_('Compañía no válida.'))
        if company not in self.env.companies:
            raise AccessError(_('No tiene acceso a esta compañía.'))

        year = int(filters.get('year') or fields.Date.context_today(self).year)
        month = str(filters.get('month') or fields.Date.context_today(self).month)
        if month not in {str(i) for i in range(1, 13)}:
            raise UserError(_('Mes no válido.'))

        date_from = filters.get('date_from') or False
        date_to = filters.get('date_to') or False
        if date_from and isinstance(date_from, str):
            date_from = fields.Date.from_string(date_from)
        if date_to and isinstance(date_to, str):
            date_to = fields.Date.from_string(date_to)

        journal_ids = filters.get('journal_ids') or []
        common = self.env['banks.weekly.balance.common']
        journals = common.search_balance_journals(
            company.id,
            journal_ids if journal_ids else None,
        )
        if not journals:
            raise UserError(_(
                'No hay diarios de banco marcados para Balances en los '
                'filtros seleccionados.'
            ))

        return {
            'company': company,
            'year': year,
            'month': month,
            'date_from': date_from,
            'date_to': date_to,
            'journal_ids': journals.ids,
            'compare_previous': bool(filters.get('compare_previous')),
            'view_mode': filters.get('view_mode') or 'dashboard',
            'group_by': filters.get('group_by') or 'week',
        }

    @api.model
    def _wizard_vals_from_filters(self, filters, parsed):
        vals = {
            'company_id': parsed['company'].id,
            'year': parsed['year'],
            'month': parsed['month'],
            'journal_ids': [(6, 0, parsed['journal_ids'])],
        }
        if parsed['date_from'] and parsed['date_to']:
            vals['date_from'] = parsed['date_from']
            vals['date_to'] = parsed['date_to']
        elif filters.get('use_custom_range'):
            raise UserError(_('Indique fecha desde y hasta para el rango personalizado.'))
        return vals

    @api.model
    def _create_wizard_from_filters(self, filters):
        """Persisted transient (needed by report_action exports)."""
        parsed = self._parse_filters(filters)
        return self.env['banks.weekly.balance.report'].create(
            self._wizard_vals_from_filters(filters, parsed)
        )

    @api.model
    def _new_wizard_from_filters(self, filters):
        """In-memory (non-persisted) wizard for read-only payload building.

        Returns ``(parsed, wizard)``. Using ``new()`` avoids an INSERT/DELETE
        of a transient record on every dashboard RPC call; the calc layer only
        reads scalar fields and journal ids from the wizard.
        """
        parsed = self._parse_filters(filters)
        wizard = self.env['banks.weekly.balance.report'].new(
            self._wizard_vals_from_filters(filters, parsed)
        )
        return parsed, wizard

    @api.model
    def get_bank_weekly_dashboard_data(self, filters):
        parsed, wizard = self._new_wizard_from_filters(filters)
        payload = self.env['banks.weekly.balance.common'].build_dashboard_payload(
            wizard,
            options={
                'compare_previous': parsed['compare_previous'],
                'group_by': parsed['group_by'],
            },
        )
        payload['view_mode'] = parsed['view_mode']
        payload['group_by'] = parsed['group_by']
        payload.pop('_aggregations', None)
        return payload

    # Grupo de gerencia requerido para ver indicadores estratégicos de salud
    # financiera (ratios, ciclo de efectivo, proyecciones, comparativos).
    _FINANCIAL_HEALTH_GROUP = 'gn_banks.banks_debit_credit_manager'

    @api.model
    def _can_view_financial_health(self):
        return self.env.su or self.env.user.has_group(self._FINANCIAL_HEALTH_GROUP)

    @api.model
    def get_bank_financial_health_data(self, filters):
        """Strategic liquidity and financial health indicators (Salud financiera tab)."""
        if not self._can_view_financial_health():
            raise AccessError(_(
                'No tiene permisos para ver los indicadores de salud financiera. '
                'Requiere el rol de gestor de débitos y créditos bancarios.'
            ))
        parsed, wizard = self._new_wizard_from_filters(filters)
        payload = self.env['banks.financial.health'].build_payload(
            wizard,
            options={
                'compare_previous': parsed['compare_previous'],
                'group_by': parsed['group_by'],
            },
        )
        payload['view_mode'] = parsed['view_mode']
        payload['group_by'] = parsed['group_by']
        return payload

    @api.model
    def get_report_data(self, filters):
        """Backward-compatible alias."""
        return self.get_bank_weekly_dashboard_data(filters)

    @api.model
    def _drilldown_domain(self, company, common, wizard, group_by, drilldown):
        """Build AML domain for drill-down preview and actions."""
        journal_ids = wizard.journal_ids
        journal = self.env['account.journal'].browse(
            drilldown.get('journal_id')
        ).exists()
        if journal and journal in journal_ids:
            accounts = journal.default_account_id
            if not accounts:
                return None, None
            account_ids = accounts.ids
            journal_label = journal.name
        else:
            accounts = journal_ids.mapped('default_account_id').filtered('id')
            if not accounts:
                return None, None
            account_ids = accounts.ids
            journal_label = _('Todos los bancos')

        _ps, _pe, ranges = common.resolve_period_and_ranges(wizard, group_by)
        week_no = int(drilldown.get('week_no') or 0)
        metric = drilldown.get('metric') or drilldown.get('row_type') or 'inflow'
        w_start = w_end = day_before = None
        for wno, ws, we in ranges:
            if wno == week_no:
                w_start, w_end = ws, we
                day_before = ws - timedelta(days=1)
                break
        if not w_start:
            return None, None

        base = common._ml_domain_base(company, account_ids)
        if metric == 'opening':
            domain = base + [('date', '<=', day_before)]
            name = _('Saldo inicial — %(j)s') % {'j': journal_label}
        elif metric == 'closing':
            domain = base + [('date', '<=', w_end)]
            name = _('Saldo final — %(j)s') % {'j': journal_label}
        elif metric == 'outflow':
            domain = base + [
                ('date', '>=', w_start),
                ('date', '<=', w_end),
                ('credit', '>', 0),
            ]
            name = _('Salidas — %(j)s') % {'j': journal_label}
        elif metric == 'net':
            domain = base + [
                ('date', '>=', w_start),
                ('date', '<=', w_end),
                '|', ('debit', '>', 0), ('credit', '>', 0),
            ]
            name = _('Movimientos netos — %(j)s') % {'j': journal_label}
        else:
            domain = base + [
                ('date', '>=', w_start),
                ('date', '<=', w_end),
                ('debit', '>', 0),
            ]
            name = _('Entradas — %(j)s') % {'j': journal_label}
        return domain, name

    @api.model
    def get_drilldown_preview(self, filters, drilldown, limit=50):
        parsed, wizard = self._new_wizard_from_filters(filters)
        company = wizard.company_id
        common = self.env['banks.weekly.balance.common']
        domain, _name = self._drilldown_domain(
            company, common, wizard, parsed['group_by'], drilldown,
        )
        if not domain:
            return {'lines': [], 'count': 0}
        aml = self.env['account.move.line']
        lines = aml.search_read(
            domain, ['date', 'name', 'debit', 'credit', 'move_id'],
            limit=limit, order='date desc, id desc',
        )
        for ln in lines:
            ln['move_name'] = ln['move_id'][1] if ln.get('move_id') else ''
        return {'lines': lines, 'count': aml.search_count(domain)}

    @api.model
    def get_drilldown_action(self, filters, drilldown):
        """Abrir apuntes contables según celda seleccionada."""
        parsed, wizard = self._new_wizard_from_filters(filters)
        company = wizard.company_id
        common = self.env['banks.weekly.balance.common']
        domain, name = self._drilldown_domain(
            company, common, wizard, parsed['group_by'], drilldown,
        )
        if not domain:
            raise UserError(_('Semana no encontrada.'))
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {
                'search_default_posted': 1,
                'expand': 1,
            },
        }

    @api.model
    def get_bank_statement_action(self, filters, drilldown):
        """Abrir líneas de extracto bancario del periodo."""
        parsed, wizard = self._new_wizard_from_filters(filters)
        common = self.env['banks.weekly.balance.common']
        journal = self.env['account.journal'].browse(
            drilldown.get('journal_id')
        ).exists()
        if not journal or journal not in wizard.journal_ids:
            raise UserError(_('Diario no válido.'))
        journal.check_access('read')

        _period_start, _period_end, ranges = common.resolve_period_and_ranges(
            wizard, parsed['group_by'],
        )
        week_no = int(drilldown.get('week_no') or 0)
        w_start = w_end = None
        for wno, ws, we in ranges:
            if wno == week_no:
                w_start, w_end = ws, we
                break
        if not w_start:
            raise UserError(_('Semana no encontrada.'))

        if 'account.bank.statement.line' not in self.env:
            raise UserError(_('Extractos bancarios no disponibles.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Extracto — %(j)s') % {'j': journal.name},
            'res_model': 'account.bank.statement.line',
            'view_mode': 'list,form',
            'domain': [
                ('journal_id', '=', journal.id),
                ('date', '>=', w_start),
                ('date', '<=', w_end),
            ],
        }

    @api.model
    def get_export_xlsx_action(self, filters):
        wizard = self._create_wizard_from_filters(filters)
        return self.env.ref(
            'gn_banks_balance.action_banks_weekly_balance_report_xlsx'
        ).report_action(wizard, data={'wizard_id': wizard.id})

    @api.model
    def get_export_html_action(self, filters):
        wizard = self._create_wizard_from_filters(filters)
        return self.env.ref(
            'gn_banks_balance.action_banks_weekly_balance_report_html'
        ).report_action(wizard)

    @api.model
    def get_export_pdf_action(self, filters):
        wizard = self._create_wizard_from_filters(filters)
        return self.env.ref(
            'gn_banks_balance.action_banks_weekly_balance_report_pdf'
        ).report_action(wizard)

    @api.model
    def get_share_url(self):
        """URL directa del dashboard (para compartir)."""
        # SUDO-JUSTIFIED: ir.config_parameter web.base.url es global del sistema
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        return '%s/odoo/banks-weekly-balance' % base.rstrip('/')
