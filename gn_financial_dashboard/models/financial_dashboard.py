# -*- coding: utf-8 -*-
"""Backend RPC para el Tablero Financiero (OWL).

Este módulo es un *companion* del módulo comercial ``bi_financial_reports_comm``
(BrowseInfo, OPL-1). NO modifica ese módulo: calcula sus propios indicadores
directamente sobre ``account.move.line`` (misma fuente que los reportes BI) y,
cuando el módulo BI está instalado, ofrece accesos directos (drill-down) a sus
reportes para el detalle.
"""
import base64
import io
from datetime import timedelta

from dateutil.relativedelta import relativedelta

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.date_utils import get_fiscal_year


# Agrupaciones por tipo de cuenta (alineadas con executive.summary.report del
# módulo BI para mantener coherencia de cifras).
INCOME_TYPES = ('income', 'income_other')
COGS_TYPES = ('expense_direct_cost',)
EXPENSE_TYPES = ('expense', 'expense_depreciation')
CASH_TYPES = ('asset_cash', 'liability_credit_card')
RECEIVABLE_TYPES = ('asset_receivable',)
PAYABLE_TYPES = ('liability_payable',)
ASSET_TYPES = (
    'asset_cash', 'asset_receivable', 'asset_current', 'asset_prepayments',
    'asset_fixed', 'asset_non_current',
)
LIABILITY_TYPES = (
    'liability_payable', 'liability_credit_card', 'liability_current',
    'liability_non_current', 'equity', 'equity_unaffected',
)
CURRENT_ASSET_TYPES = (
    'asset_cash', 'asset_receivable', 'asset_current', 'asset_prepayments',
)
QUICK_ASSET_TYPES = ('asset_cash', 'asset_receivable', 'asset_prepayments')
CURRENT_LIABILITY_TYPES = (
    'liability_payable', 'liability_credit_card', 'liability_current',
)

# Cuentas analíticas: tipos a los que aplica el filtro analitico/proyecto.
# Solo se usan en P&L (income/cogs/expenses); el resto (balance, cartera,
# flujo) sigue calculandose por account.move.line sin analitica.
ANALYTIC_TYPES = INCOME_TYPES + COGS_TYPES + EXPENSE_TYPES


# report_type del módulo BI -> xmlid de la acción cliente (para drill-down).
BI_REPORT_ACTIONS = {
    'profit_and_loss': 'bi_financial_reports_comm.profit_and_loss_action',
    'balance_sheet': 'bi_financial_reports_comm.balance_sheet_action',
    'general_ledger': 'bi_financial_reports_comm.general_ledger_action',
    'cash_flow': 'bi_financial_reports_comm.cash_flow_action',
    'executive_summary': 'bi_financial_reports_comm.executive_summary_action',
    'aged_receivable': 'bi_financial_reports_comm.partner_ageing_receivable_action',
    'aged_payable': 'bi_financial_reports_comm.partner_ageing_payable_action',
}


class GnFinancialDashboard(models.AbstractModel):
    _name = 'gn.financial.dashboard'
    _description = 'Tablero financiero interactivo (OWL)'

    # ------------------------------------------------------------------
    # Opciones de filtros
    # ------------------------------------------------------------------
    @api.model
    def get_filter_options(self, company_id=None):
        company = self.env['res.company'].browse(
            company_id or self.env.company.id
        )
        if not company.exists():
            raise UserError(_('Compañía no válida.'))
        company.check_access('read')

        today = fields.Date.context_today(self)
        fy_from, fy_to = get_fiscal_year(today)
        # search_read en lugar de search + acceso a .name: evita el prefetch
        # de todos los campos almacenados de account.journal (más eficiente y
        # robusto frente a campos huérfanos en registros desactualizados).
        journals = self.env['account.journal'].search_read(
            [('company_id', 'child_of', company.id)], ['name'], order='name'
        )

        # Dimensiones extra (solo si el modulo/campo correspondiente existe).
        caps = self._dimension_capabilities()
        branches = []
        if caps['branch']:
            branches = self.env['res.branch'].sudo().search_read(
                [('company_id', 'child_of', company.id)], ['name'], order='name',
            )
        analytics_payload = []
        if caps['analytic']:
            # Agrupamos por plan para que el UI los muestre por categoria.
            plans = self.env['account.analytic.plan'].sudo().search([], order='sequence,name')
            accounts = self.env['account.analytic.account'].sudo().search_read(
                ['|', ('company_id', '=', False), ('company_id', 'child_of', company.id)],
                ['name', 'plan_id', 'code'], order='plan_id,name',
            )
            by_plan = {}
            for acc in accounts:
                pid = acc['plan_id'][0] if acc.get('plan_id') else False
                by_plan.setdefault(pid, []).append({
                    'id': acc['id'],
                    'name': '%s%s' % (
                        ('[' + acc['code'] + '] ') if acc.get('code') else '',
                        acc.get('name') or '',
                    ),
                })
            for p in plans:
                ids_in_plan = by_plan.get(p.id, [])
                if not ids_in_plan:
                    continue
                analytics_payload.append({
                    'plan_id': p.id,
                    'plan_name': p.name,
                    'accounts': ids_in_plan,
                })
            # Cuentas sin plan (poco frecuente, pero por robustez).
            if by_plan.get(False):
                analytics_payload.append({
                    'plan_id': False,
                    'plan_name': _('Sin plan'),
                    'accounts': by_plan[False],
                })
        projects = []
        if caps['project']:
            projects = self.env['project.project'].sudo().search_read(
                [
                    '|', ('company_id', '=', False),
                    ('company_id', 'child_of', company.id),
                ],
                ['name', 'analytic_account_id'], order='name',
            )
            # Solo proyectos con cuenta analitica (los demas no podrian
            # filtrar el P&L; los descartamos para evitar dudas).
            projects = [
                {'id': p['id'], 'name': p['name']}
                for p in projects if p.get('analytic_account_id')
            ]

        return {
            'company_id': company.id,
            'companies': [
                {'id': c.id, 'name': c.name} for c in self.env.companies
            ],
            'multi_company': len(self.env.companies) > 1,
            'currency': self._currency_payload(company.currency_id),
            'date_from': fields.Date.to_string(fy_from),
            'date_to': fields.Date.to_string(today),
            'fiscalyear_from': fields.Date.to_string(fy_from),
            'fiscalyear_to': fields.Date.to_string(fy_to),
            'journals': [{'id': j['id'], 'name': j['name']} for j in journals],
            'target_move_options': [
                {'id': 'posted', 'name': _('Solo asentado')},
                {'id': 'all', 'name': _('Todos (incl. borrador)')},
            ],
            'comparison_options': [
                {'id': 'previous_period', 'name': _('Período anterior')},
                {'id': 'same_last_year', 'name': _('Mismo período año anterior')},
                {'id': 'none', 'name': _('Sin comparación')},
            ],
            'period_length_options': [
                {'id': 15, 'name': _('15 días')},
                {'id': 30, 'name': _('30 días')},
                {'id': 45, 'name': _('45 días')},
                {'id': 60, 'name': _('60 días')},
            ],
            'has_bi_reports': self._has_bi_reports(),
            # Dimensiones extra y sus payloads.
            'dimensions': caps,
            'branches': [
                {'id': b['id'], 'name': b['name']} for b in branches
            ],
            'analytic_plans': analytics_payload,
            'projects': projects,
            # V20 Fase 4: capacidades por área (ventas/compras/inventario +
            # paneles personalizados registrados vía hook).
            'areas': self._area_capabilities(),
        }

    def _currency_payload(self, currency):
        return {
            'id': currency.id,
            'symbol': currency.symbol or currency.name or '',
            'position': currency.position or 'before',
            'decimal_places': currency.decimal_places,
        }

    def _has_bi_reports(self):
        return bool(self.env['ir.module.module'].sudo().search_count([
            ('name', '=', 'bi_financial_reports_comm'),
            ('state', '=', 'installed'),
        ]))

    # ------------------------------------------------------------------
    # Parseo / validación de filtros
    # ------------------------------------------------------------------
    @api.model
    def _parse_filters(self, filters):
        filters = filters or {}
        company = self.env['res.company'].browse(
            filters.get('company_id') or self.env.company.id
        )
        if not company.exists():
            raise UserError(_('Compañía no válida.'))
        company.check_access('read')

        date_from = fields.Date.from_string(filters.get('date_from')) if filters.get('date_from') else None
        date_to = fields.Date.from_string(filters.get('date_to')) if filters.get('date_to') else None
        if not date_from or not date_to:
            today = fields.Date.context_today(self)
            fy_from, _fy_to = get_fiscal_year(today)
            date_from = date_from or fy_from
            date_to = date_to or today
        if date_from > date_to:
            raise UserError(_('La fecha inicial no puede ser mayor que la final.'))

        journal_ids = filters.get('journal_ids') or []
        if journal_ids:
            journals = self.env['account.journal'].browse(journal_ids).exists()
            journals.check_access('read')
            journal_ids = journals.ids

        target_move = filters.get('target_move') or 'posted'
        if target_move not in ('posted', 'all'):
            target_move = 'posted'
        comparison = filters.get('comparison') or 'previous_period'
        if comparison not in ('previous_period', 'same_last_year', 'none'):
            comparison = 'previous_period'

        # Dimensiones opcionales (deteccion suave: solo se aplican si el
        # modulo/campo correspondiente esta instalado).
        caps = self._dimension_capabilities()
        branch_ids = []
        if caps['branch']:
            raw_branch = filters.get('branch_ids') or []
            if raw_branch:
                branches = self.env['res.branch'].browse(raw_branch).exists()
                branches.check_access('read')
                branch_ids = branches.ids

        analytic_account_ids = []
        if caps['analytic']:
            raw_analytic = filters.get('analytic_account_ids') or []
            if raw_analytic:
                accs = self.env['account.analytic.account'].browse(raw_analytic).exists()
                accs.check_access('read')
                analytic_account_ids = accs.ids

        project_ids = []
        # Si hay proyectos seleccionados los convertimos a sus cuentas
        # analiticas y los fusionamos con analytic_account_ids para usar una
        # sola ruta de calculo aguas abajo.
        if caps['project']:
            raw_projects = filters.get('project_ids') or []
            if raw_projects:
                projects = self.env['project.project'].browse(raw_projects).exists()
                projects.check_access('read')
                project_ids = projects.ids
                proj_analytic_ids = [
                    p.analytic_account_id.id for p in projects
                    if p.analytic_account_id
                ]
                if proj_analytic_ids:
                    analytic_account_ids = list(
                        set(analytic_account_ids + proj_analytic_ids)
                    )

        period_length = int(filters.get('period_length') or 30)
        if period_length not in (15, 30, 45, 60):
            period_length = 30

        return {
            'company': company,
            'date_from': date_from,
            'date_to': date_to,
            'journal_ids': journal_ids,
            'target_move': target_move,
            'comparison': comparison,
            'branch_ids': branch_ids,
            'analytic_account_ids': analytic_account_ids,
            'project_ids': project_ids,
            'caps': caps,
            'period_length': period_length,
        }

    def _dimension_capabilities(self):
        """Detecta qué dimensiones extra están disponibles en el sistema.

        Se basa en la presencia de campos/modelos para activarlas sin romper
        cuando faltan los modulos opcionales.
        """
        AML = self.env['account.move.line']
        env = self.env
        has_branch = (
            'branch_id' in AML._fields
            and 'res.branch' in env
        )
        has_analytic = 'account.analytic.account' in env
        has_project = 'project.project' in env
        return {
            'branch': bool(has_branch),
            'analytic': bool(has_analytic),
            'project': bool(has_project),
        }

    def _comparison_dates(self, date_from, date_to, comparison):
        if comparison == 'none':
            return None
        if comparison == 'same_last_year':
            return (
                date_from - relativedelta(years=1),
                date_to - relativedelta(years=1),
            )
        # previous_period: ventana contigua del mismo número de días.
        span = (date_to - date_from).days
        prev_to = date_from - timedelta(days=1)
        prev_from = prev_to - timedelta(days=span)
        return prev_from, prev_to

    # ------------------------------------------------------------------
    # Acceso a datos contables
    # ------------------------------------------------------------------
    def _base_domain(self, parsed):
        domain = [
            ('company_id', 'child_of', parsed['company'].id),
            ('display_type', 'not in', ('line_section', 'line_note')),
        ]
        if parsed['target_move'] == 'posted':
            domain.append(('parent_state', '=', 'posted'))
        else:
            domain.append(('parent_state', 'in', ('posted', 'draft')))
        if parsed['journal_ids']:
            domain.append(('journal_id', 'in', parsed['journal_ids']))
        # Filtro por sucursal (cuando el campo existe y hay seleccion).
        if parsed.get('branch_ids') and parsed.get('caps', {}).get('branch'):
            domain.append(('branch_id', 'in', parsed['branch_ids']))
        return domain

    def _has_analytic_filter(self, parsed):
        """¿La consulta debe restringirse a cuentas analiticas?"""
        return bool(parsed.get('analytic_account_ids'))

    def _account_type_map(self, company):
        # Pequeño cache por compañia/registro: evita repetir la consulta cuando
        # varios helpers la piden dentro del mismo request.
        key = ('_gn_fd_type_map', company.id)
        cache = getattr(self.env, '_gn_fd_request_cache', None)
        if cache is None:
            cache = {}
            try:
                self.env._gn_fd_request_cache = cache
            except Exception:
                cache = None
        if cache is not None and key in cache:
            return cache[key]
        accounts = self.env['account.account'].with_context(active_test=False).search_read(
            [('company_ids', 'in', company.id)], ['account_type'],
        )
        result = {a['id']: a['account_type'] for a in accounts}
        if cache is not None:
            cache[key] = result
        return result

    def _account_name_map(self, account_ids):
        if not account_ids:
            return {}
        recs = self.env['account.account'].browse(list(account_ids)).read(
            ['code', 'name']
        )
        return {
            r['id']: ('%s %s' % (r.get('code') or '', r.get('name') or '')).strip()
            for r in recs
        }

    def _per_account_sums(self, parsed, date_from, date_to, from_beginning=False):
        """Devuelve {account_id: {'balance','debit','credit'}} en el rango.

        ``from_beginning=True`` ignora ``date_from`` (saldo acumulado hasta
        ``date_to``), útil para cuentas de balance.

        Cuando ``parsed`` tiene un filtro analitico activo el P&L se calcula
        desde ``account.analytic.line`` (ruta performante en Odoo 19); el
        resto de tipos de cuenta (balance, cartera, efectivo) se sigue
        calculando por ``account.move.line``.
        """
        domain = self._base_domain(parsed)
        if not from_beginning and date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))
        rows = self.env['account.move.line']._read_group(
            domain, groupby=['account_id'],
            aggregates=['balance:sum', 'debit:sum', 'credit:sum'],
        )
        result = {}
        for account, balance, debit, credit in rows:
            result[account.id] = {
                'balance': float(balance or 0.0),
                'debit': float(debit or 0.0),
                'credit': float(credit or 0.0),
            }
        # Si hay filtro analitico, reemplazamos los tipos de P&L con los
        # importes provenientes de account.analytic.line para ese rango.
        if self._has_analytic_filter(parsed):
            analytic = self._analytic_pl_sums(parsed, date_from, date_to, from_beginning)
            type_map = self._account_type_map(parsed['company'])
            pl_accounts = {
                aid for aid, t in type_map.items()
                if t in ANALYTIC_TYPES
            }
            # Vaciar las cuentas P&L (se recalculan desde analitica).
            for aid in list(result):
                if aid in pl_accounts:
                    result.pop(aid, None)
            for aid, vals in analytic.items():
                result[aid] = vals
        return result

    def _analytic_pl_sums(self, parsed, date_from, date_to, from_beginning=False):
        """P&L por cuenta proveniente de ``account.analytic.line``.

        Solo cuentas con ``general_account_id`` en tipos de resultado. Se
        agrupa por ``general_account_id`` y se devuelve la misma estructura
        que ``_per_account_sums`` (balance/debit/credit).

        Convencion en Odoo: una linea analitica con ``amount`` positivo
        equivale a un debito en la cuenta general, y un ``amount`` negativo
        a un credito. ``balance`` = ``-amount`` para alinearse con el signo
        contable usado por el resto del calculo.
        """
        analytic_ids = parsed['analytic_account_ids']
        if not analytic_ids:
            return {}
        type_map = self._account_type_map(parsed['company'])
        pl_account_ids = [
            aid for aid, t in type_map.items() if t in ANALYTIC_TYPES
        ]
        if not pl_account_ids:
            return {}
        # Construimos el dominio respetando compañía, diario y target_move
        # (cuando aplica) y restringiendo a las cuentas analiticas activas.
        # move_line_id != False asegura que solo consideramos lineas atadas a
        # un asiento contable (descartando lineas de timesheet sin asiento).
        states = ['posted'] if parsed['target_move'] == 'posted' else ['posted', 'draft']
        domain = [
            ('company_id', 'child_of', parsed['company'].id),
            ('general_account_id', 'in', pl_account_ids),
            ('move_line_id', '!=', False),
            ('move_line_id.parent_state', 'in', states),
            ('auto_account_id', 'in', analytic_ids),
        ]
        if parsed.get('journal_ids'):
            domain.append(('journal_id', 'in', parsed['journal_ids']))
        if parsed.get('branch_ids') and parsed.get('caps', {}).get('branch'):
            # branch_id en analytic.line se obtiene a traves de move_line.
            domain.append(('move_line_id.branch_id', 'in', parsed['branch_ids']))
        if not from_beginning and date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))

        rows = self.env['account.analytic.line']._read_group(
            domain, groupby=['general_account_id'],
            aggregates=['amount:sum'],
        )
        out = {}
        for account, amount in rows:
            amt = float(amount or 0.0)
            # amount>0 = debito; amount<0 = credito. Balance contable = -amount.
            balance = -amt
            debit = amt if amt > 0 else 0.0
            credit = -amt if amt < 0 else 0.0
            out[account.id] = {
                'balance': balance,
                'debit': debit,
                'credit': credit,
            }
        return out

    def _analytic_monthly_balance(self, parsed, account_ids, date_from, date_to):
        """Suma mensual de ``balance`` (=-amount) por mes para los ``account_ids``.

        Misma logica de signos que ``_analytic_pl_sums``. Devuelve
        ``{'YYYY-MM': balance}``.
        """
        if not account_ids or not parsed.get('analytic_account_ids'):
            return {}
        states = ['posted'] if parsed['target_move'] == 'posted' else ['posted', 'draft']
        domain = [
            ('company_id', 'child_of', parsed['company'].id),
            ('general_account_id', 'in', account_ids),
            ('move_line_id', '!=', False),
            ('move_line_id.parent_state', 'in', states),
            ('auto_account_id', 'in', parsed['analytic_account_ids']),
            ('date', '>=', date_from), ('date', '<=', date_to),
        ]
        if parsed.get('journal_ids'):
            domain.append(('journal_id', 'in', parsed['journal_ids']))
        if parsed.get('branch_ids') and parsed.get('caps', {}).get('branch'):
            domain.append(('move_line_id.branch_id', 'in', parsed['branch_ids']))
        rows = self.env['account.analytic.line']._read_group(
            domain, groupby=['date:month'], aggregates=['amount:sum'],
        )
        out = {}
        for month, amount in rows:
            key = month.strftime('%Y-%m') if month else False
            out[key] = -float(amount or 0.0)
        return out

    def _sum_types(self, per_account, type_map, types, key='balance'):
        types = set(types)
        return sum(
            vals.get(key, 0.0)
            for aid, vals in per_account.items()
            if type_map.get(aid) in types
        )

    # ------------------------------------------------------------------
    # KPIs
    # ------------------------------------------------------------------
    def _kpis_for_period(self, parsed, type_map, date_from, date_to):
        strict = self._per_account_sums(parsed, date_from, date_to)
        asof = self._per_account_sums(parsed, date_from, date_to, from_beginning=True)

        revenue = -self._sum_types(strict, type_map, INCOME_TYPES)
        cogs = self._sum_types(strict, type_map, COGS_TYPES)
        expenses = self._sum_types(strict, type_map, EXPENSE_TYPES)
        gross_profit = revenue - cogs
        net_profit = gross_profit - expenses

        cash_received = self._sum_types(strict, type_map, CASH_TYPES, key='debit')
        cash_spent = self._sum_types(strict, type_map, CASH_TYPES, key='credit')
        cash_surplus = cash_received - cash_spent

        closing_bank = self._sum_types(asof, type_map, CASH_TYPES)
        receivables = self._sum_types(asof, type_map, RECEIVABLE_TYPES)
        payables = -self._sum_types(asof, type_map, PAYABLE_TYPES)
        total_assets = self._sum_types(asof, type_map, ASSET_TYPES)
        total_liab = self._sum_types(asof, type_map, LIABILITY_TYPES)
        net_assets = total_assets + total_liab

        current_assets = self._sum_types(asof, type_map, CURRENT_ASSET_TYPES)
        quick_assets = self._sum_types(asof, type_map, QUICK_ASSET_TYPES)
        current_liab = -self._sum_types(asof, type_map, CURRENT_LIABILITY_TYPES)
        working_capital = current_assets - current_liab

        def pct(part, whole):
            return (part / whole * 100.0) if whole else 0.0

        # ----- KPIs avanzados (#6) -----
        config_maps = self._config_account_maps(parsed['company'])
        # Gasto por intereses (con signo positivo: importe positivo = gasto).
        interest_expense = self._sum_account_ids(
            strict, config_maps['interest']
        ) if config_maps['interest'] else 0.0
        # Impuestos sobre la renta.
        tax_expense = self._sum_account_ids(
            strict, config_maps['tax']
        ) if config_maps['tax'] else 0.0
        # Depreciación: por defecto suma cuentas de tipo expense_depreciation;
        # si el usuario configuró cuentas explícitas, las agrega.
        depreciation_default = self._sum_types(
            strict, type_map, ('expense_depreciation',)
        )
        depreciation_extra = self._sum_account_ids(
            strict, config_maps['depreciation']
        ) if config_maps['depreciation'] else 0.0
        depreciation = depreciation_default + depreciation_extra

        ebit = net_profit + interest_expense + tax_expense
        ebitda = ebit + depreciation

        # Inventario promedio = (inicial + final) / 2.
        inventory_close = self._sum_account_ids(asof, config_maps['inventory']) \
            if config_maps['inventory'] else 0.0
        inventory_open = self._opening_balance_account_ids(
            parsed, config_maps['inventory'], date_from,
        ) if config_maps['inventory'] else 0.0
        inventory_avg = (inventory_open + inventory_close) / 2.0

        # Saldos iniciales para promedios de activos / CxC / CxP.
        assets_open = self._opening_balance_types(parsed, type_map, ASSET_TYPES, date_from)
        rec_open = self._opening_balance_types(parsed, type_map, RECEIVABLE_TYPES, date_from)
        pay_open = -self._opening_balance_types(parsed, type_map, PAYABLE_TYPES, date_from)
        equity_close = -self._sum_types(asof, type_map, ('equity', 'equity_unaffected'))
        equity_open = -self._opening_balance_types(
            parsed, type_map, ('equity', 'equity_unaffected'), date_from,
        )
        equity_avg = (equity_open + equity_close) / 2.0
        assets_avg = (assets_open + total_assets) / 2.0
        receivables_avg = (rec_open + receivables) / 2.0
        payables_avg = (pay_open + payables) / 2.0

        # Rotaciones (veces en el período). Si el saldo promedio es <= 0
        # (no hay base de CxC/CxP/inventario) la rotación no aplica → 0.
        inv_turnover = (cogs / inventory_avg) if inventory_avg > 0 else 0.0
        ar_turnover = (revenue / receivables_avg) if receivables_avg > 0 else 0.0
        ap_turnover = ((cogs + expenses) / payables_avg) if payables_avg > 0 else 0.0
        assets_turnover = (revenue / assets_avg) if assets_avg > 0 else 0.0

        # Apalancamiento financiero: activos / patrimonio (promedios).
        # Patrimonio negativo (crisis) → ratio no representativo: devuelve 0.
        leverage_ratio = (assets_avg / equity_avg) if equity_avg > 0 else 0.0
        # Cobertura de intereses: EBIT / gasto financiero.
        interest_coverage = (ebit / interest_expense) if interest_expense else 0.0
        # Margen operativo / EBITDA sobre ventas.
        operating_margin = pct(ebit, revenue)
        ebitda_margin = pct(ebitda, revenue)
        # ROA / ROE con saldos promedio (más estables que el saldo final).
        roa = pct(net_profit, assets_avg)
        roe = pct(net_profit, equity_avg)

        return {
            'revenue': revenue,
            'cogs': cogs,
            'gross_profit': gross_profit,
            'expenses': expenses,
            'net_profit': net_profit,
            'gross_margin': pct(gross_profit, revenue),
            'net_margin': pct(net_profit, revenue),
            'roi': pct(net_profit, total_assets),
            'cash_received': cash_received,
            'cash_spent': cash_spent,
            'cash_surplus': cash_surplus,
            'closing_bank': closing_bank,
            'receivables': receivables,
            'payables': payables,
            'total_assets': total_assets,
            'net_assets': net_assets,
            'working_capital': working_capital,
            'current_assets': current_assets,
            'current_liab': current_liab,
            'quick_assets': quick_assets,
            'current_ratio': (current_assets / current_liab) if current_liab else 0.0,
            'quick_ratio': (quick_assets / current_liab) if current_liab else 0.0,
            # ----- Nuevos KPIs (V20 Fase 1) -----
            'interest_expense': interest_expense,
            'tax_expense': tax_expense,
            'depreciation': depreciation,
            'ebit': ebit,
            'ebitda': ebitda,
            'operating_margin': operating_margin,
            'ebitda_margin': ebitda_margin,
            'roa': roa,
            'roe': roe,
            'assets_turnover': round(assets_turnover, 2),
            'inventory_turnover': round(inv_turnover, 2),
            'ar_turnover': round(ar_turnover, 2),
            'ap_turnover': round(ap_turnover, 2),
            'leverage_ratio': round(leverage_ratio, 2),
            'interest_coverage': round(interest_coverage, 2),
            '_strict': strict,
            '_type_map': type_map,
        }

    def _config_account_maps(self, company):
        """Devuelve el mapeo de cuentas declarado por el usuario en config.

        Usa ``get_or_create`` para no romper si nunca se abrió la pantalla.
        """
        config = self.env['gn.financial.dashboard.config'].sudo().get_or_create(company)
        return {
            'interest': set(config.interest_account_ids.ids),
            'tax': set(config.tax_expense_account_ids.ids),
            'depreciation': set(config.depreciation_account_ids.ids),
            'inventory': set(config.inventory_account_ids.ids),
        }

    def _sum_account_ids(self, per_account, account_ids, key='balance'):
        """Como ``_sum_types`` pero por conjunto de account_id explícito."""
        if not account_ids:
            return 0.0
        ids = set(account_ids)
        return sum(
            v.get(key, 0.0)
            for aid, v in per_account.items() if aid in ids
        )

    def _opening_balance_types(self, parsed, type_map, types, date_from):
        """Saldo acumulado anterior a ``date_from`` para los tipos dados."""
        if not date_from:
            return 0.0
        prev_to = date_from - timedelta(days=1)
        per = self._per_account_sums(parsed, None, prev_to, from_beginning=True)
        return self._sum_types(per, type_map, types)

    def _opening_balance_account_ids(self, parsed, account_ids, date_from):
        """Saldo acumulado anterior a ``date_from`` para cuentas explícitas."""
        if not date_from or not account_ids:
            return 0.0
        prev_to = date_from - timedelta(days=1)
        per = self._per_account_sums(parsed, None, prev_to, from_beginning=True)
        return self._sum_account_ids(per, account_ids)

    # ------------------------------------------------------------------
    # Series mensuales (rentabilidad)
    # ------------------------------------------------------------------
    def _monthly_series(self, parsed, type_map, date_from, date_to):
        income_ids = [aid for aid, t in type_map.items() if t in INCOME_TYPES]
        expense_ids = [
            aid for aid, t in type_map.items()
            if t in COGS_TYPES or t in EXPENSE_TYPES
        ]
        analytic_mode = self._has_analytic_filter(parsed)

        if analytic_mode:
            income_by_month = self._analytic_monthly_balance(
                parsed, income_ids, date_from, date_to,
            )
            expense_by_month = self._analytic_monthly_balance(
                parsed, expense_ids, date_from, date_to,
            )
        else:
            domain = self._base_domain(parsed) + [
                ('date', '>=', date_from), ('date', '<=', date_to),
            ]

            def grouped(extra):
                rows = self.env['account.move.line']._read_group(
                    domain + extra, groupby=['date:month'],
                    aggregates=['balance:sum'],
                )
                out = {}
                for month, balance in rows:
                    key = month.strftime('%Y-%m') if month else False
                    out[key] = float(balance or 0.0)
                return out

            income_by_month = grouped([('account_id', 'in', income_ids)]) if income_ids else {}
            expense_by_month = grouped([('account_id', 'in', expense_ids)]) if expense_ids else {}

        labels, income, expense, net = [], [], [], []
        cursor = date_from.replace(day=1)
        month_names = [
            _('Ene'), _('Feb'), _('Mar'), _('Abr'), _('May'), _('Jun'),
            _('Jul'), _('Ago'), _('Sep'), _('Oct'), _('Nov'), _('Dic'),
        ]
        while cursor <= date_to:
            key = cursor.strftime('%Y-%m')
            inc = -income_by_month.get(key, 0.0)
            exp = expense_by_month.get(key, 0.0)
            labels.append('%s %s' % (month_names[cursor.month - 1], cursor.year))
            income.append(round(inc, 2))
            expense.append(round(exp, 2))
            net.append(round(inc - exp, 2))
            cursor = cursor + relativedelta(months=1)
        return {
            'labels': labels,
            'income': income,
            'expense': expense,
            'net': net,
        }

    # ------------------------------------------------------------------
    # Waterfall de resultados
    # ------------------------------------------------------------------
    def _waterfall(self, kpis):
        return [
            {'label': _('Ingresos'), 'value': round(kpis['revenue'], 2), 'type': 'total'},
            {'label': _('Costo de ventas'), 'value': round(-kpis['cogs'], 2), 'type': 'down'},
            {'label': _('Utilidad bruta'), 'value': round(kpis['gross_profit'], 2), 'type': 'subtotal'},
            {'label': _('Gastos'), 'value': round(-kpis['expenses'], 2), 'type': 'down'},
            {'label': _('Utilidad neta'), 'value': round(kpis['net_profit'], 2), 'type': 'subtotal'},
        ]

    # ------------------------------------------------------------------
    # Composición de gastos (dona)
    # ------------------------------------------------------------------
    def _expense_breakdown(self, kpis, limit=8):
        strict = kpis['_strict']
        type_map = kpis['_type_map']
        exp = {
            aid: vals['balance']
            for aid, vals in strict.items()
            if type_map.get(aid) in COGS_TYPES or type_map.get(aid) in EXPENSE_TYPES
        }
        exp = {aid: v for aid, v in exp.items() if abs(v) > 0.009}
        names = self._account_name_map(exp.keys())
        ordered = sorted(exp.items(), key=lambda kv: abs(kv[1]), reverse=True)
        labels, values, account_ids = [], [], []
        for aid, val in ordered[:limit]:
            labels.append(names.get(aid, str(aid)))
            values.append(round(val, 2))
            account_ids.append(aid)
        rest = ordered[limit:]
        if rest:
            labels.append(_('Otros'))
            values.append(round(sum(v for _a, v in rest), 2))
            account_ids.append(False)
        return {'labels': labels, 'values': values, 'account_ids': account_ids}

    # ------------------------------------------------------------------
    # Cartera vencida (cobrar / pagar)
    # ------------------------------------------------------------------
    # Etiquetas y semáforo de tramos (alineados con índices 0..5).
    AGING_COLORS = ('#198754', '#f1c40f', '#f1c40f', '#e67e22', '#e67e22', '#dc3545')

    def _aging_labels(self, period_length):
        pl = int(period_length or 30)
        return (
            _('No vencido'),
            _('1-%s') % pl,
            _('%s-%s') % (pl + 1, 2 * pl),
            _('%s-%s') % (2 * pl + 1, 3 * pl),
            _('%s-%s') % (3 * pl + 1, 4 * pl),
            _('+%s') % (4 * pl + 1),
        )

    def _aging_bucket_case_sql(self, period_length):
        """CASE SQL para clasificar tramos; ``period_length`` validado (15/30/45/60)."""
        pl = int(period_length)
        p1, p2, p3, p4 = pl, 2 * pl, 3 * pl, 4 * pl
        return (
            "CASE "
            "WHEN COALESCE(aml.date_maturity, aml.date) >= %(on_date)s THEN 0 "
            f"WHEN %(on_date)s - COALESCE(aml.date_maturity, aml.date) BETWEEN 1 AND {p1} THEN 1 "
            f"WHEN %(on_date)s - COALESCE(aml.date_maturity, aml.date) BETWEEN {p1 + 1} AND {p2} THEN 2 "
            f"WHEN %(on_date)s - COALESCE(aml.date_maturity, aml.date) BETWEEN {p2 + 1} AND {p3} THEN 3 "
            f"WHEN %(on_date)s - COALESCE(aml.date_maturity, aml.date) BETWEEN {p3 + 1} AND {p4} THEN 4 "
            "ELSE 5 END"
        )

    def _company_ids(self, parsed):
        return tuple(self.env['res.company'].search(
            [('id', 'child_of', parsed['company'].id)]
        ).ids) or (parsed['company'].id,)

    def _aging_sql_where(self, parsed, account_types):
        """WHERE + params comunes para aging/rankings sobre cuentas conciliables."""
        states = ('posted',) if parsed['target_move'] == 'posted' else ('posted', 'draft')
        params = {
            'company_ids': self._company_ids(parsed),
            'on_date': parsed['date_to'],
            'states': tuple(states),
            'types': tuple(account_types),
        }
        where = (
            "aml.company_id IN %(company_ids)s "
            "AND aml.parent_state IN %(states)s "
            "AND aml.date <= %(on_date)s "
            "AND acc.account_type IN %(types)s "
        )
        if parsed['journal_ids']:
            where += "AND aml.journal_id IN %(journal_ids)s "
            params['journal_ids'] = tuple(parsed['journal_ids'])
        if parsed.get('branch_ids') and parsed.get('caps', {}).get('branch'):
            where += "AND aml.branch_id IN %(branch_ids)s "
            params['branch_ids'] = tuple(parsed['branch_ids'])
        return where, params

    def _aging_resid_from(self, where):
        """Reconstruye el saldo de cada línea a la fecha de corte (como reporte nativo)."""
        from_sql = (
            "FROM account_move_line aml "
            "JOIN account_account acc ON acc.id = aml.account_id "
            "LEFT JOIN (SELECT debit_move_id AS mid, SUM(amount) AS amt "
            "           FROM account_partial_reconcile "
            "           WHERE max_date > %(on_date)s GROUP BY debit_move_id) pdadj "
            "       ON pdadj.mid = aml.id "
            "LEFT JOIN (SELECT credit_move_id AS mid, SUM(amount) AS amt "
            "           FROM account_partial_reconcile "
            "           WHERE max_date > %(on_date)s GROUP BY credit_move_id) pcadj "
            "       ON pcadj.mid = aml.id "
        )
        resid_expr = (
            "(aml.amount_residual + COALESCE(pdadj.amt, 0) - COALESCE(pcadj.amt, 0))"
        )
        candidate = (
            where
            + "AND (aml.amount_residual != 0 OR pdadj.mid IS NOT NULL "
            "OR pcadj.mid IS NOT NULL) "
        )
        return from_sql, resid_expr, candidate

    def _aging_side(self, parsed, account_types, sign):
        where, params = self._aging_sql_where(parsed, account_types)
        from_sql, resid, candidate = self._aging_resid_from(where)
        bucket_case = self._aging_bucket_case_sql(parsed['period_length'])
        self.env.cr.execute(
            """
            SELECT bucket, SUM(resid) AS amt FROM (
                SELECT """ + bucket_case + """ AS bucket,
                       """ + resid + """ AS resid
                """ + from_sql + """
                WHERE """ + candidate + """
            ) t
            WHERE resid != 0
            GROUP BY bucket
            """,
            params,
        )
        totals = [0.0] * 6
        for bucket, amt in self.env.cr.fetchall():
            totals[bucket] = sign * float(amt or 0.0)
        total = sum(totals)
        pct = [round((v / total * 100.0), 1) if total else 0.0 for v in totals]
        labels = self._aging_labels(parsed['period_length'])
        return {
            'labels': list(labels),
            'values': [round(v, 2) for v in totals],
            'pct': pct,
            'colors': list(self.AGING_COLORS),
            'total': round(total, 2),
            'overdue': round(sum(totals[1:]), 2),
            'over_120': round(totals[5], 2),
        }

    def _aging(self, parsed):
        return {
            'receivable': self._aging_side(parsed, RECEIVABLE_TYPES, 1.0),
            'payable': self._aging_side(parsed, PAYABLE_TYPES, -1.0),
        }

    def _aging_resid_line_ids(self, parsed, account_types, partner_id=None):
        """IDs de apuntes con saldo distinto de cero a la fecha de corte."""
        where, params = self._aging_sql_where(parsed, account_types)
        from_sql, resid, candidate = self._aging_resid_from(where)
        pred = candidate
        if partner_id:
            pred += "AND aml.partner_id = %(drill_partner)s "
            params['drill_partner'] = partner_id
        self.env.cr.execute(
            "SELECT id FROM (SELECT aml.id AS id, " + resid + " AS resid "
            + from_sql + " WHERE " + pred + ") t WHERE resid != 0",
            params,
        )
        return [r[0] for r in self.env.cr.fetchall()]

    # ------------------------------------------------------------------
    # Rankings de terceros (clientes por cobrar / proveedores por pagar)
    # ------------------------------------------------------------------
    def _partner_ranking_side(self, parsed, account_types, sign, limit=500):
        where, params = self._aging_sql_where(parsed, account_types)
        params['limit'] = limit
        from_sql, resid, candidate = self._aging_resid_from(where)
        partner_pred = candidate + "AND aml.partner_id IS NOT NULL "
        self.env.cr.execute(
            """
            SELECT partner_id,
                   SUM(resid) AS pending,
                   SUM(CASE WHEN mdate < %(on_date)s THEN resid ELSE 0 END) AS overdue,
                   SUM(resid * GREATEST(%(on_date)s - mdate, 0)) AS wdays
            FROM (
                SELECT aml.partner_id AS partner_id,
                       COALESCE(aml.date_maturity, aml.date) AS mdate,
                       """ + resid + """ AS resid
                """ + from_sql + """
                WHERE """ + partner_pred + """
            ) t
            WHERE resid != 0
            GROUP BY partner_id
            ORDER BY ABS(SUM(resid)) DESC
            LIMIT %(limit)s
            """,
            params,
        )
        rows = self.env.cr.fetchall()
        partner_ids = [r[0] for r in rows]
        names = {}
        if partner_ids:
            for p in self.env['res.partner'].browse(partner_ids).read(['display_name']):
                names[p['id']] = p['display_name']
        self.env.cr.execute(
            "SELECT SUM(resid) FROM ("
            "  SELECT " + resid + " AS resid "
            + from_sql +
            "  WHERE " + partner_pred +
            ") t WHERE resid != 0",
            params,
        )
        grand = sign * float((self.env.cr.fetchone() or [0.0])[0] or 0.0)
        items = []
        for partner_id, pending_raw, overdue_raw, wdays_raw in rows:
            pending = sign * float(pending_raw or 0.0)
            overdue = sign * float(overdue_raw or 0.0)
            avg_days = (float(wdays_raw or 0.0) / float(pending_raw)) if pending_raw else 0.0
            items.append({
                'partner_id': partner_id,
                'name': names.get(partner_id, _('(Sin nombre)')),
                'pending': round(pending, 2),
                'overdue': round(overdue, 2),
                'avg_days': round(avg_days, 1),
                'pct': round((pending / grand * 100.0), 1) if grand else 0.0,
            })
        return {'items': items, 'total': round(grand, 2)}

    def _partner_rankings(self, parsed, limit=500):
        return {
            'receivable': self._partner_ranking_side(parsed, RECEIVABLE_TYPES, 1.0, limit=limit),
            'payable': self._partner_ranking_side(parsed, PAYABLE_TYPES, -1.0, limit=limit),
        }

    # ------------------------------------------------------------------
    # Ranking de gastos (Top N con % y variación)
    # ------------------------------------------------------------------
    def _expense_ranking(self, kpis, prev_strict=None, limit=10):
        strict = kpis['_strict']
        type_map = kpis['_type_map']
        exp = {
            aid: vals['balance']
            for aid, vals in strict.items()
            if type_map.get(aid) in COGS_TYPES or type_map.get(aid) in EXPENSE_TYPES
        }
        exp = {aid: v for aid, v in exp.items() if abs(v) > 0.009}
        total = sum(exp.values())
        names = self._account_name_map(exp.keys())
        ordered = sorted(exp.items(), key=lambda kv: abs(kv[1]), reverse=True)
        items = []
        for aid, val in ordered[:limit]:
            prev_val = None
            delta_pct = None
            if prev_strict is not None:
                prev_val = prev_strict.get(aid, {}).get('balance', 0.0)
                if prev_val:
                    delta_pct = round((val - prev_val) / abs(prev_val) * 100.0, 1)
            items.append({
                'account_id': aid,
                'name': names.get(aid, str(aid)),
                'amount': round(val, 2),
                'pct': round((val / total * 100.0), 1) if total else 0.0,
                'delta_pct': delta_pct,
            })
        return {'items': items, 'total': round(total, 2)}

    # ------------------------------------------------------------------
    # Indicadores de cobranza y pago
    # ------------------------------------------------------------------
    def _collection_indicators(self, parsed, kpis, aging_rec):
        strict = kpis['_strict']
        type_map = kpis['_type_map']
        period_days = (parsed['date_to'] - parsed['date_from']).days + 1
        invoiced = sum(
            v['debit'] for aid, v in strict.items()
            if type_map.get(aid) in RECEIVABLE_TYPES
        )
        collected = sum(
            v['credit'] for aid, v in strict.items()
            if type_map.get(aid) in RECEIVABLE_TYPES
        )
        receivables = kpis['receivables']
        total = (aging_rec or {}).get('total') or 0.0
        overdue = (aging_rec or {}).get('overdue') or 0.0
        over120 = (aging_rec or {}).get('over_120') or 0.0
        revenue = kpis['revenue']
        dso = (receivables * period_days / revenue) if revenue else 0.0
        return {
            'dso': round(dso, 1),
            'overdue_pct': round((overdue / total * 100.0), 1) if total else 0.0,
            'over_120_pct': round((over120 / total * 100.0), 1) if total else 0.0,
            'collected': round(collected, 2),
            'invoiced': round(invoiced, 2),
            'collection_ratio': round((collected / invoiced * 100.0), 1) if invoiced else 0.0,
        }

    def _payment_indicators(self, parsed, kpis, aging_pay):
        strict = kpis['_strict']
        type_map = kpis['_type_map']
        period_days = (parsed['date_to'] - parsed['date_from']).days + 1
        purchased = sum(
            v['credit'] for aid, v in strict.items()
            if type_map.get(aid) in PAYABLE_TYPES
        )
        paid = sum(
            v['debit'] for aid, v in strict.items()
            if type_map.get(aid) in PAYABLE_TYPES
        )
        payables = kpis['payables']
        total = (aging_pay or {}).get('total') or 0.0
        overdue = (aging_pay or {}).get('overdue') or 0.0
        cogs_plus_exp = kpis['cogs'] + kpis['expenses']
        dpo = (payables * period_days / cogs_plus_exp) if cogs_plus_exp else 0.0
        return {
            'dpo': round(dpo, 1),
            'overdue_pct': round((overdue / total * 100.0), 1) if total else 0.0,
            'paid': round(paid, 2),
            'purchased': round(purchased, 2),
            'payment_ratio': round((paid / purchased * 100.0), 1) if purchased else 0.0,
        }

    # ------------------------------------------------------------------
    # Salud financiera y alertas
    # ------------------------------------------------------------------
    def _health_and_alerts(self, kpis, aging, thresholds, trends=None, data_quality=None):
        """Calcula puntaje y alertas delegando en el motor de scoring.

        El motor (``gn.financial.dashboard.scoring``) produce el desglose
        explicable por categorías; aquí se mantiene la firma original para no
        romper consumidores (PDF/Excel/UI antigua) y se enriquece el payload
        con las claves nuevas (``categories``, ``risk``, ``radar``,
        ``recommendations``, ``decisions``).
        """
        engine = self.env['gn.financial.dashboard.scoring']
        return engine.compute(kpis, aging, thresholds,
                              trends=trends, data_quality=data_quality)

    # ------------------------------------------------------------------
    # Tendencias (dirección + racha) por KPI desde serie mensual
    # ------------------------------------------------------------------
    # KPIs cuya tendencia analizamos a partir de movimientos mensuales.
    _TREND_KEYS = ('revenue', 'expenses', 'net_profit', 'cash_surplus',
                   'cash_received', 'cash_spent')

    def _trends(self, parsed, type_map):
        """Calcula la dirección y la racha por KPI desde la serie mensual.

        Devuelve ``{kpi_key: {direction, streak_months, label, series}}``.
        - ``direction`` ∈ ``up`` | ``down`` | ``flat``: dirección consistente
          de los últimos meses.
        - ``streak_months``: meses consecutivos con la misma dirección.
        - ``label``: texto resumen ya traducido para la UI.
        - ``series``: últimos valores (numéricos) para mini-gráficos.
        """
        # Reutilizamos la serie mensual de P&L para ingresos/gastos/neto.
        s = self._monthly_series(parsed, type_map,
                                 parsed['date_from'], parsed['date_to'])
        # Serie mensual de flujo de caja (entradas/salidas).
        cf = self._cashflow(parsed, type_map)
        # Mapeo KPI -> serie (lista numérica) y etiqueta.
        series_by_key = {
            'revenue': (s.get('income') or [], _('Ingresos')),
            'expenses': (s.get('expense') or [], _('Gastos')),
            'net_profit': (s.get('net') or [], _('Utilidad neta')),
            'cash_surplus': (cf.get('net') or [], _('Flujo de caja')),
            'cash_received': (cf.get('inflow') or [], _('Cobros')),
            'cash_spent': (cf.get('outflow') or [], _('Pagos')),
        }
        out = {}
        for key in self._TREND_KEYS:
            data, label = series_by_key.get(key, ([], ''))
            out[key] = self._trend_meta(data, label)
        return out

    def _trend_meta(self, series, label):
        """Calcula dirección + racha para una serie mensual."""
        clean = [float(v or 0.0) for v in series if v is not None]
        if len(clean) < 2:
            return {
                'direction': 'flat',
                'streak_months': 0,
                'label': _('Sin tendencia disponible'),
                'series': clean,
            }
        # Diferencias punto a punto; descartamos pequeñas variaciones (<2%
        # respecto al promedio absoluto) para evitar falsos positivos.
        avg_abs = sum(abs(v) for v in clean) / len(clean) or 1.0
        eps = max(avg_abs * 0.02, 0.5)
        deltas = [clean[i] - clean[i - 1] for i in range(1, len(clean))]
        # Racha hacia atrás: contamos meses consecutivos con misma dirección.
        last = deltas[-1]
        if abs(last) <= eps:
            direction = 'flat'
            streak = 0
        else:
            direction = 'up' if last > 0 else 'down'
            streak = 1
            for d in reversed(deltas[:-1]):
                if direction == 'up' and d > eps:
                    streak += 1
                elif direction == 'down' and d < -eps:
                    streak += 1
                else:
                    break
        if direction == 'up':
            text = _('%s creciendo durante %d mes(es)') % (label, streak)
        elif direction == 'down':
            text = _('%s bajando durante %d mes(es)') % (label, streak)
        else:
            text = _('%s estable') % label
        return {
            'direction': direction,
            'streak_months': streak,
            'label': text,
            'series': clean[-12:],
        }

    # ------------------------------------------------------------------
    # Flujo de caja (método directo)
    # ------------------------------------------------------------------
    # Mapeo de account_type de la contrapartida -> categoría de flujo.
    CASHFLOW_CATEGORY = {
        'income': 'operating', 'income_other': 'operating',
        'expense': 'operating', 'expense_direct_cost': 'operating',
        'expense_depreciation': 'operating',
        'asset_receivable': 'operating', 'liability_payable': 'operating',
        'asset_current': 'operating', 'liability_current': 'operating',
        'asset_prepayments': 'operating',
        'asset_fixed': 'investing', 'asset_non_current': 'investing',
        'liability_non_current': 'financing', 'equity': 'financing',
        'equity_unaffected': 'financing',
    }

    def _cashflow(self, parsed, type_map):
        date_from, date_to = parsed['date_from'], parsed['date_to']
        cash_ids = [aid for aid, t in type_map.items() if t in CASH_TYPES]
        empty = {
            'labels': [], 'inflow': [], 'outflow': [], 'net': [], 'cumulative': [],
            'opening': 0.0, 'closing': 0.0,
            'operating': 0.0, 'investing': 0.0, 'financing': 0.0,
        }
        if not cash_ids:
            return empty

        # Serie mensual: entradas (débitos) y salidas (créditos) en efectivo.
        domain = self._base_domain(parsed) + [
            ('account_id', 'in', cash_ids),
            ('date', '>=', date_from), ('date', '<=', date_to),
        ]
        rows = self.env['account.move.line']._read_group(
            domain, groupby=['date:month'], aggregates=['debit:sum', 'credit:sum'],
        )
        by_month = {}
        for month, debit, credit in rows:
            key = month.strftime('%Y-%m') if month else False
            by_month[key] = (float(debit or 0.0), float(credit or 0.0))

        # Saldo inicial: acumulado de efectivo antes de date_from.
        open_domain = self._base_domain(parsed) + [
            ('account_id', 'in', cash_ids), ('date', '<', date_from),
        ]
        open_rows = self.env['account.move.line']._read_group(
            open_domain, groupby=[], aggregates=['balance:sum'],
        )
        opening = float(open_rows[0][0] or 0.0) if open_rows else 0.0

        labels, inflow, outflow, net, cumulative = [], [], [], [], []
        running = opening
        cursor = date_from.replace(day=1)
        month_names = [
            _('Ene'), _('Feb'), _('Mar'), _('Abr'), _('May'), _('Jun'),
            _('Jul'), _('Ago'), _('Sep'), _('Oct'), _('Nov'), _('Dic'),
        ]
        while cursor <= date_to:
            key = cursor.strftime('%Y-%m')
            inc, out = by_month.get(key, (0.0, 0.0))
            n = inc - out
            running += n
            labels.append('%s %s' % (month_names[cursor.month - 1], cursor.year))
            inflow.append(round(inc, 2))
            outflow.append(round(out, 2))
            net.append(round(n, 2))
            cumulative.append(round(running, 2))
            cursor = cursor + relativedelta(months=1)

        cats = self._cashflow_by_category(parsed)
        return {
            'labels': labels,
            'inflow': inflow,
            'outflow': outflow,
            'net': net,
            'cumulative': cumulative,
            'opening': round(opening, 2),
            'closing': round(running, 2),
            'operating': round(cats.get('operating', 0.0), 2),
            'investing': round(cats.get('investing', 0.0), 2),
            'financing': round(cats.get('financing', 0.0), 2),
        }

    def _cashflow_by_category(self, parsed):
        """Clasifica el flujo por la naturaleza de las contrapartidas.

        Aproximación de método directo: a cada movimiento de efectivo se le
        asocia el tipo de cuenta de su(s) contrapartida(s). Para asientos con
        múltiples líneas de efectivo el reparto es aproximado.
        """
        states = ('posted',) if parsed['target_move'] == 'posted' else ('posted', 'draft')
        params = {
            'company_ids': self._company_ids(parsed),
            'date_from': parsed['date_from'],
            'date_to': parsed['date_to'],
            'states': tuple(states),
            'cash_types': tuple(CASH_TYPES),
        }
        where_journal = ''
        if parsed['journal_ids']:
            where_journal = 'AND cash.journal_id IN %(journal_ids)s '
            params['journal_ids'] = tuple(parsed['journal_ids'])
        where_branch = ''
        if parsed.get('branch_ids') and parsed.get('caps', {}).get('branch'):
            where_branch = 'AND cash.branch_id IN %(branch_ids)s '
            params['branch_ids'] = tuple(parsed['branch_ids'])
        self.env.cr.execute(
            """
            SELECT oacc.account_type, SUM(-cp.balance)
            FROM account_move_line cash
            JOIN account_account cacc ON cacc.id = cash.account_id
                AND cacc.account_type IN %(cash_types)s
            JOIN account_move_line cp ON cp.move_id = cash.move_id AND cp.id != cash.id
            JOIN account_account oacc ON oacc.id = cp.account_id
                AND oacc.account_type NOT IN %(cash_types)s
            WHERE cash.company_id IN %(company_ids)s
              AND cash.parent_state IN %(states)s
              AND cash.date >= %(date_from)s AND cash.date <= %(date_to)s
              """ + where_journal + where_branch + """
            GROUP BY oacc.account_type
            """,
            params,
        )
        cats = {'operating': 0.0, 'investing': 0.0, 'financing': 0.0}
        for account_type, amount in self.env.cr.fetchall():
            cat = self.CASHFLOW_CATEGORY.get(account_type, 'operating')
            cats[cat] += float(amount or 0.0)
        return cats

    # ------------------------------------------------------------------
    # Análisis financiero automático (texto reutilizable en PDF/Excel)
    # ------------------------------------------------------------------
    def _financial_analysis(self, kpis, aging, collection, payment, cashflow, compare):
        notes = []

        def add(tone, text):
            notes.append({'tone': tone, 'text': text})

        if kpis['net_profit'] > 0:
            add('positive', _('La utilidad neta es positiva (%s), lo que indica rentabilidad en el período.') % self._fmt_amount(kpis['net_profit']))
        elif kpis['net_profit'] < 0:
            add('negative', _('La utilidad neta es negativa (%s); los gastos superan los ingresos.') % self._fmt_amount(kpis['net_profit']))

        nm = kpis['net_margin']
        if compare and compare.get('kpis'):
            prev_nm = compare['kpis'].get('net_margin', 0.0)
            if nm >= prev_nm:
                add('positive', _('El margen neto (%.1f%%) se mantiene o mejora frente al período anterior (%.1f%%).') % (nm, prev_nm))
            else:
                add('warning', _('El margen neto (%.1f%%) bajó respecto al período anterior (%.1f%%).') % (nm, prev_nm))
        else:
            add('info', _('El margen neto del período es %.1f%%.') % nm)

        if cashflow and cashflow.get('closing') is not None:
            if kpis['cash_surplus'] < 0:
                add('warning', _('El flujo de caja es negativo; conviene revisar la cobranza o los pagos.'))
            else:
                add('positive', _('El flujo de caja es positivo, con un saldo final de %s.') % self._fmt_amount(cashflow['closing']))

        rec = aging.get('receivable') or {}
        if rec.get('total'):
            over120_pct = (rec.get('over_120', 0.0) / rec['total'] * 100.0) if rec['total'] else 0.0
            if over120_pct > 10:
                add('warning', _('La cartera a más de 120 días representa el %.1f%% del total por cobrar: riesgo de recuperación.') % over120_pct)

        if kpis['revenue']:
            exp_ratio = kpis['expenses'] / kpis['revenue'] * 100.0
            if exp_ratio > 60:
                add('warning', _('Los gastos representan el %.1f%% de los ingresos.') % exp_ratio)
            else:
                add('info', _('Los gastos representan el %.1f%% de los ingresos.') % exp_ratio)

        if collection and collection.get('dso'):
            add('info', _('El plazo medio de cobro (DSO) es de %.0f días.') % collection['dso'])
        if payment and payment.get('dpo'):
            add('info', _('El plazo medio de pago (DPO) es de %.0f días.') % payment['dpo'])

        return notes

    def _fmt_amount(self, value):
        return '%s %s' % (
            self.env.company.currency_id.symbol or '',
            '{:,.2f}'.format(value or 0.0),
        )

    # ------------------------------------------------------------------
    # Calidad de datos contables
    # ------------------------------------------------------------------
    def _data_quality(self, parsed):
        company_ids = list(self._company_ids(parsed))
        date_from, date_to = parsed['date_from'], parsed['date_to']
        AML = self.env['account.move.line']
        base = [
            ('company_id', 'in', company_ids),
            ('date', '>=', date_from), ('date', '<=', date_to),
            ('parent_state', '=', 'posted'),
            ('display_type', 'not in', ('line_section', 'line_note')),
        ]
        checks = []

        no_partner = AML.search_count(base + [
            ('account_id.account_type', 'in', list(RECEIVABLE_TYPES + PAYABLE_TYPES)),
            ('partner_id', '=', False),
        ])
        if no_partner:
            checks.append({'severity': 'warning', 'title': _('Apuntes sin tercero'),
                           'message': _('%d apuntes en cuentas por cobrar/pagar sin tercero.') % no_partner,
                           'count': no_partner})

        # Asientos descuadrados (suma de balance != 0 por asiento).
        self.env.cr.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT move_id FROM account_move_line
                WHERE company_id IN %(cids)s AND date BETWEEN %(df)s AND %(dt)s
                  AND parent_state = 'posted'
                GROUP BY move_id HAVING ROUND(SUM(balance)::numeric, 2) != 0
            ) t
            """,
            {'cids': tuple(company_ids), 'df': date_from, 'dt': date_to},
        )
        unbalanced = self.env.cr.fetchone()[0]
        if unbalanced:
            checks.append({'severity': 'danger', 'title': _('Asientos descuadrados'),
                           'message': _('%d asientos con débito ≠ crédito.') % unbalanced,
                           'count': unbalanced})

        # Cuentas por cobrar/pagar con residual y sin fecha de vencimiento.
        no_maturity = AML.search_count(base + [
            ('account_id.account_type', 'in', list(RECEIVABLE_TYPES + PAYABLE_TYPES)),
            ('amount_residual', '!=', 0.0),
            ('date_maturity', '=', False),
        ])
        if no_maturity:
            checks.append({'severity': 'warning', 'title': _('Sin fecha de vencimiento'),
                           'message': _('%d apuntes con saldo y sin fecha de vencimiento.') % no_maturity,
                           'count': no_maturity})

        # Saldos negativos inusuales en bancos/caja.
        type_map = self._account_type_map(parsed['company'])
        cash_ids = [aid for aid, t in type_map.items() if t in CASH_TYPES]
        neg_cash = 0
        if cash_ids:
            asof = self._per_account_sums(parsed, None, date_to, from_beginning=True)
            neg_cash = sum(
                1 for aid in cash_ids
                if asof.get(aid, {}).get('balance', 0.0) < -0.01
            )
        if neg_cash:
            checks.append({'severity': 'warning', 'title': _('Bancos en negativo'),
                           'message': _('%d cuentas de banco/caja con saldo negativo.') % neg_cash,
                           'count': neg_cash})

        return {'checks': checks, 'ok': not checks}

    # ------------------------------------------------------------------
    # Estado de cierre contable
    # ------------------------------------------------------------------
    def _closing_status(self, parsed):
        company_ids = list(self._company_ids(parsed))
        date_from, date_to = parsed['date_from'], parsed['date_to']
        Move = self.env['account.move']
        base = [
            ('company_id', 'in', company_ids),
            ('date', '>=', date_from), ('date', '<=', date_to),
        ]
        posted = Move.search_count(base + [('state', '=', 'posted')])
        draft = Move.search_count(base + [('state', '=', 'draft')])

        last = Move.search_read(
            [('company_id', 'in', company_ids), ('state', '=', 'posted')],
            ['date'], order='date desc', limit=1,
        )
        last_date = last[0]['date'] if last else False

        # Meses del rango sin movimientos publicados.
        rows = self.env['account.move.line']._read_group(
            [('company_id', 'in', company_ids),
             ('date', '>=', date_from), ('date', '<=', date_to),
             ('parent_state', '=', 'posted')],
            groupby=['date:month'], aggregates=['__count'],
        )
        months_with = set()
        for month, _count in rows:
            if month:
                months_with.add(month.strftime('%Y-%m'))
        empty_months = []
        cursor = date_from.replace(day=1)
        while cursor <= date_to:
            key = cursor.strftime('%Y-%m')
            if key not in months_with:
                empty_months.append(key)
            cursor = cursor + relativedelta(months=1)

        return {
            'posted': posted,
            'draft': draft,
            'last_date': fields.Date.to_string(last_date) if last_date else False,
            'empty_months': empty_months,
            'has_draft': bool(draft),
        }

    # ------------------------------------------------------------------
    # Configuración y capacidades
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_config(self, company_id=None):
        """Devuelve la configuración fusionada (compañía + preferencias del usuario)."""
        company = self.env['res.company'].browse(
            company_id or self.env.company.id
        )
        if not company.exists():
            raise UserError(_('Compañía no válida.'))
        return self._build_config_payload(company)

    def _build_config_payload(self, company):
        """Fusiona la config de compañía con las preferencias del usuario."""
        config = self.env['gn.financial.dashboard.config'].get_or_create(company)
        base = config.to_payload()
        pref = self.env['gn.financial.dashboard.user.pref'].get_or_create_for(
            user=self.env.user, company=company)
        return pref.apply_to_payload(base)

    @api.model
    def save_user_pref(self, values):
        """Guarda las preferencias del usuario actual desde la UI (sin abrir form).

        ``values`` admite cualquier campo del modelo ``user.pref``.
        Devuelve el payload de configuración actualizado para refrescar la UI.
        """
        company = self.env.company
        pref = self.env['gn.financial.dashboard.user.pref'].get_or_create_for(
            user=self.env.user, company=company)
        if values:
            allowed = set(pref._fields.keys()) - {'id', 'user_id', 'company_id'}
            payload = {k: v for k, v in values.items() if k in allowed}
            if payload:
                pref.write(payload)
        return self._build_config_payload(company)

    def _capabilities(self):
        """Capacidades del usuario actual (gating de export/config/detalle)."""
        is_manager = self.env.user.has_group('account.group_account_manager')
        caps = {
            'is_manager': is_manager,
            'can_export': is_manager,
            'can_configure': is_manager,
            'can_view_detail': is_manager,
        }
        caps.update(self._dimension_capabilities())
        return caps

    def _kpi_meta(self):
        """Explicación contable por KPI para los tooltips de ayuda.

        Cada entrada describe qué es el indicador, cómo se calcula, qué tipos
        de cuenta usa y cómo interpretarlo.
        """
        return {
            'revenue': {
                'title': _('Ingresos'),
                'desc': _('Total de ventas e ingresos del período.'),
                'formula': _('Suma (con signo positivo) de cuentas de ingreso.'),
                'accounts': _("account_type: 'income', 'income_other'"),
                'hint': _('Mayor es mejor; refleja el volumen de operación.'),
            },
            'cogs': {
                'title': _('Costo de ventas'),
                'desc': _('Costo directo asociado a los ingresos.'),
                'formula': _('Suma de cuentas de costo directo.'),
                'accounts': _("account_type: 'expense_direct_cost'"),
                'hint': _('Se resta de los ingresos para la utilidad bruta.'),
            },
            'gross_profit': {
                'title': _('Utilidad bruta'),
                'desc': _('Resultado tras descontar el costo de ventas.'),
                'formula': _('Ingresos − Costo de ventas.'),
                'accounts': _('Ingresos menos costo directo.'),
                'hint': _('Indica eficiencia operativa antes de gastos.'),
            },
            'expenses': {
                'title': _('Gastos'),
                'desc': _('Gastos operativos del período.'),
                'formula': _('Suma de cuentas de gasto y depreciación.'),
                'accounts': _("account_type: 'expense', 'expense_depreciation'"),
                'hint': _('Una reducción suele ser favorable.'),
            },
            'net_profit': {
                'title': _('Utilidad neta'),
                'desc': _('Resultado final del período.'),
                'formula': _('Utilidad bruta − Gastos.'),
                'accounts': _('Ingresos − costo − gastos.'),
                'hint': _('Positiva indica rentabilidad.'),
            },
            'gross_margin': {
                'title': _('Margen bruto'),
                'desc': _('Utilidad bruta como % de los ingresos.'),
                'formula': _('Utilidad bruta / Ingresos × 100.'),
                'accounts': _('Derivado de ingresos y costo.'),
                'hint': _('Mide rentabilidad antes de gastos.'),
            },
            'net_margin': {
                'title': _('Margen neto'),
                'desc': _('Utilidad neta como % de los ingresos.'),
                'formula': _('Utilidad neta / Ingresos × 100.'),
                'accounts': _('Derivado de la utilidad neta.'),
                'hint': _('Mide rentabilidad final del negocio.'),
            },
            'roi': {
                'title': _('ROI'),
                'desc': _('Retorno sobre los activos.'),
                'formula': _('Utilidad neta / Activos totales × 100.'),
                'accounts': _('Utilidad neta sobre activos.'),
                'hint': _('Eficiencia en el uso de los activos.'),
            },
            'cash_surplus': {
                'title': _('Flujo de caja'),
                'desc': _('Efectivo neto generado en el período.'),
                'formula': _('Entradas − salidas en cuentas de efectivo.'),
                'accounts': _("account_type: 'asset_cash', 'liability_credit_card'"),
                'hint': _('Positivo indica generación de efectivo.'),
            },
            'closing_bank': {
                'title': _('Saldo bancario'),
                'desc': _('Saldo acumulado en bancos y caja al corte.'),
                'formula': _('Saldo de cuentas de efectivo hasta la fecha final.'),
                'accounts': _("account_type: 'asset_cash', 'liability_credit_card'"),
                'hint': _('Disponibilidad de efectivo.'),
            },
            'receivables': {
                'title': _('Cuentas por cobrar'),
                'desc': _('Saldo pendiente de clientes.'),
                'formula': _('Saldo de cuentas por cobrar a la fecha final.'),
                'accounts': _("account_type: 'asset_receivable'"),
                'hint': _('Crece con ventas a crédito; vigilar cobranza.'),
            },
            'payables': {
                'title': _('Cuentas por pagar'),
                'desc': _('Saldo pendiente con proveedores.'),
                'formula': _('Saldo de cuentas por pagar a la fecha final.'),
                'accounts': _("account_type: 'liability_payable'"),
                'hint': _('Una reducción suele ser favorable.'),
            },
            'working_capital': {
                'title': _('Capital de trabajo'),
                'desc': _('Holgura de liquidez de corto plazo.'),
                'formula': _('Activo corriente − Pasivo corriente.'),
                'accounts': _('Activos y pasivos corrientes.'),
                'hint': _('Positivo indica capacidad de cubrir obligaciones.'),
            },
            'current_ratio': {
                'title': _('Razón corriente'),
                'desc': _('Cobertura del pasivo corriente.'),
                'formula': _('Activo corriente / Pasivo corriente.'),
                'accounts': _('Activos y pasivos corrientes.'),
                'hint': _('> 1 indica solvencia de corto plazo.'),
            },
            # Gráficos / paneles (no son KPIs pero comparten la misma estructura
            # para reutilizar el componente InfoTip).
            'chart_monthly': {
                'title': _('Evolución mensual'),
                'desc': _('Ingresos, gastos y utilidad neta mes a mes del período.'),
                'formula': _('Suma de cuentas de resultado por mes.'),
                'accounts': _('Ingresos, costos, gastos y depreciación.'),
                'hint': _('Permite identificar tendencias y estacionalidad.'),
            },
            'chart_waterfall': {
                'title': _('Cascada de resultados'),
                'desc': _('Descompone los ingresos en utilidad neta restando costos y gastos.'),
                'formula': _('Ingresos − Costo de ventas − Gastos = Utilidad neta.'),
                'accounts': _('Mismas cuentas del estado de resultados.'),
                'hint': _('Las barras descendentes muestran impacto de cada concepto.'),
            },
            'chart_expense_breakdown': {
                'title': _('Composición de gastos'),
                'desc': _('Distribución de los gastos del período por cuenta.'),
                'formula': _('Top 8 cuentas por monto + “Otros”.'),
                'accounts': _("account_type: 'expense', 'expense_depreciation', 'expense_direct_cost'"),
                'hint': _('Detecta los principales rubros de gasto.'),
            },
            'chart_cashflow': {
                'title': _('Flujo de caja mensual'),
                'desc': _('Entradas, salidas y saldo acumulado de bancos/caja por mes.'),
                'formula': _('Débito − Crédito en cuentas de efectivo.'),
                'accounts': _("account_type: 'asset_cash', 'liability_credit_card'"),
                'hint': _('El saldo acumulado refleja la liquidez disponible.'),
            },
            'chart_aging_receivable': {
                'title': _('Cartera por cobrar — antigüedad'),
                'desc': _('Saldos pendientes de clientes agrupados por días vencidos.'),
                'formula': _('Sumatoria de amount_residual por tramo.'),
                'accounts': _("account_type: 'asset_receivable'"),
                'hint': _('Tramos >120 días indican riesgo de recuperación.'),
            },
            'chart_aging_payable': {
                'title': _('Cartera por pagar — antigüedad'),
                'desc': _('Saldos pendientes con proveedores agrupados por días vencidos.'),
                'formula': _('Sumatoria de amount_residual por tramo.'),
                'accounts': _("account_type: 'liability_payable'"),
                'hint': _('Indica obligaciones por antigüedad.'),
            },
            'radar': {
                'title': _('Radar financiero'),
                'desc': _('Vista 360° con el puntaje 0-100 de cada dimensión analizada.'),
                'formula': _('Score por dimensión del motor de scoring.'),
                'accounts': _('Combinación de varios KPIs y aging.'),
                'hint': _('Mayor área = mejor desempeño global.'),
            },
            'risk': {
                'title': _('Indicador de riesgo'),
                'desc': _('Velocímetro derivado del score global y dimensiones críticas.'),
                'formula': _('0.55 × score + 0.45 × min(liquidez, flujo, cobranza).'),
                'accounts': _('Liquidez, flujo de caja, cobranza, rentabilidad.'),
                'hint': _('Verde = bajo riesgo; rojo = riesgo crítico.'),
            },
            'quick_ratio': {
                'title': _('Prueba ácida'),
                'desc': _('Liquidez inmediata sin inventarios.'),
                'formula': _('(Efectivo + por cobrar + anticipos) / Pasivo corriente.'),
                'accounts': _("asset_cash, asset_receivable, asset_prepayments"),
                'hint': _('Mide liquidez sin depender de inventario.'),
            },
            # ---- KPIs avanzados V20 Fase 1 ----
            'ebit': {
                'title': _('EBIT'),
                'desc': _('Utilidad operativa antes de intereses e impuestos.'),
                'formula': _('Utilidad neta + Intereses + Impuestos.'),
                'accounts': _('Resultado + cuentas de intereses e impuestos configuradas.'),
                'hint': _('Mide la utilidad de la operación sin financiamiento ni fiscalidad.'),
            },
            'ebitda': {
                'title': _('EBITDA'),
                'desc': _('EBIT más depreciación y amortización.'),
                'formula': _('EBIT + Depreciación + Amortización.'),
                'accounts': _('EBIT + account_type expense_depreciation y cuentas configuradas.'),
                'hint': _('Indicador clásico de generación de efectivo operativo.'),
            },
            'operating_margin': {
                'title': _('Margen operativo'),
                'desc': _('EBIT como % de los ingresos.'),
                'formula': _('EBIT / Ingresos × 100.'),
                'accounts': _('Derivado de EBIT y revenue.'),
                'hint': _('Eficiencia operativa por encima del margen neto.'),
            },
            'ebitda_margin': {
                'title': _('Margen EBITDA'),
                'desc': _('EBITDA como % de los ingresos.'),
                'formula': _('EBITDA / Ingresos × 100.'),
                'accounts': _('Derivado de EBITDA y revenue.'),
                'hint': _('Útil para comparar rentabilidad entre empresas con distinta deuda.'),
            },
            'roa': {
                'title': _('ROA'),
                'desc': _('Rentabilidad sobre los activos promedio.'),
                'formula': _('Utilidad neta / Activos promedio × 100.'),
                'accounts': _('Utilidad neta sobre activos (saldo inicial + final)/2.'),
                'hint': _('Mejor que ROI porque usa saldos promedio.'),
            },
            'roe': {
                'title': _('ROE'),
                'desc': _('Rentabilidad sobre el patrimonio promedio.'),
                'formula': _('Utilidad neta / Patrimonio promedio × 100.'),
                'accounts': _('Utilidad neta sobre patrimonio (cuentas equity).'),
                'hint': _('Mide el retorno generado para los socios.'),
            },
            'assets_turnover': {
                'title': _('Rotación de activos'),
                'desc': _('Veces que los activos generan ingresos en el período.'),
                'formula': _('Ingresos / Activos promedio.'),
                'accounts': _('Ingresos sobre activos.'),
                'hint': _('Mayor rotación = mayor eficiencia en el uso del activo.'),
            },
            'inventory_turnover': {
                'title': _('Rotación de inventarios'),
                'desc': _('Veces que el inventario se vendió en el período.'),
                'formula': _('Costo de ventas / Inventario promedio.'),
                'accounts': _('Cuentas de inventario configuradas.'),
                'hint': _('Requiere configurar las cuentas de inventario en la pestaña Cuentas.'),
            },
            'ar_turnover': {
                'title': _('Rotación de cuentas por cobrar'),
                'desc': _('Veces que la cartera se cobró en el período.'),
                'formula': _('Ingresos / Cuentas por cobrar promedio.'),
                'accounts': _("account_type: 'asset_receivable'"),
                'hint': _('Mayor rotación indica mejor cobranza.'),
            },
            'ap_turnover': {
                'title': _('Rotación de cuentas por pagar'),
                'desc': _('Veces que se pagó a proveedores en el período.'),
                'formula': _('(Costo + Gastos) / Cuentas por pagar promedio.'),
                'accounts': _("account_type: 'liability_payable'"),
                'hint': _('Equilibrar con la rotación de cobranza para no estresar la caja.'),
            },
            'leverage_ratio': {
                'title': _('Apalancamiento financiero'),
                'desc': _('Razón Activos / Patrimonio promedio.'),
                'formula': _('Activos promedio / Patrimonio promedio.'),
                'accounts': _('Activos y patrimonio (cuentas equity).'),
                'hint': _('Valores altos implican mayor dependencia de deuda.'),
            },
            'interest_coverage': {
                'title': _('Cobertura de intereses'),
                'desc': _('Veces que el EBIT cubre el gasto financiero.'),
                'formula': _('EBIT / Intereses.'),
                'accounts': _('EBIT sobre cuentas de intereses configuradas.'),
                'hint': _('> 1 indica capacidad de cubrir el costo financiero.'),
            },
            'interest_expense': {
                'title': _('Gasto por intereses'),
                'desc': _('Costo financiero del período.'),
                'formula': _('Suma de las cuentas de intereses configuradas.'),
                'accounts': _('Cuentas configuradas en la pestaña Cuentas.'),
                'hint': _('Base para calcular EBIT y cobertura de intereses.'),
            },
            'tax_expense': {
                'title': _('Impuesto sobre la renta'),
                'desc': _('Gasto por impuesto sobre la renta del período.'),
                'formula': _('Suma de las cuentas de impuesto configuradas.'),
                'accounts': _('Cuentas configuradas en la pestaña Cuentas.'),
                'hint': _('Base para calcular EBIT (utilidad neta + impuestos + intereses).'),
            },
            'depreciation': {
                'title': _('Depreciación y amortización'),
                'desc': _('D&A del período.'),
                'formula': _('Cuentas expense_depreciation + cuentas configuradas.'),
                'accounts': _("account_type: 'expense_depreciation'"),
                'hint': _('Diferencia entre EBIT y EBITDA.'),
            },
        }

    # ------------------------------------------------------------------
    # Motor de análisis de variaciones (#7)
    # ------------------------------------------------------------------
    # KPIs candidatos al análisis de variación con su impacto en utilidad
    # ('income' = positivo, 'expense' = negativo). Solo se analizan estos.
    _VARIANCE_KPIS = (
        ('revenue', 'income'),
        ('cogs', 'expense'),
        ('expenses', 'expense'),
        ('net_profit', 'derived'),
    )

    def _variance_analysis(self, parsed, type_map, kpis, compare, prev_strict, cur_strict=None):
        """Descompone la variación de KPIs clave vs. el período comparativo.

        Para cada KPI con variación absoluta significativa (>= 1% del valor
        actual o un umbral fijo) se identifican las top 5 cuentas, los top 3
        clientes/proveedores y la magnitud que cada uno aportó al delta.

        Devuelve una lista ordenada por magnitud absoluta:

        ``[{'kpi','label','current','previous','delta','delta_pct','direction',
            'accounts':[{'name','delta','share'}],
            'partners':[{'name','delta','share'}],
            'narrative': '...'}]``

        Se usa en la pestaña Diagnóstico y alimenta la narrativa ejecutiva.
        """
        if not compare or not prev_strict:
            return []
        cmp_dates = self._comparison_dates(
            parsed['date_from'], parsed['date_to'], parsed['comparison']
        )
        if not cmp_dates:
            return []

        kpi_labels = {
            'revenue': _('Ingresos'),
            'cogs': _('Costo de ventas'),
            'expenses': _('Gastos'),
            'net_profit': _('Utilidad neta'),
        }
        # Tipos de cuenta por KPI (para filtrar el _read_group).
        kpi_types = {
            'revenue': INCOME_TYPES,
            'cogs': COGS_TYPES,
            'expenses': EXPENSE_TYPES,
            'net_profit': INCOME_TYPES + COGS_TYPES + EXPENSE_TYPES,
        }
        results = []
        # Reutilizamos el strict ya calculado en kpis si está disponible
        # (evita una consulta repetida a account.move.line).
        if cur_strict is None:
            cur_strict = kpis.get('_strict') if isinstance(kpis, dict) else None
        for kpi_key, _kind in self._VARIANCE_KPIS:
            cur = kpis.get(kpi_key) or 0.0
            prev = (compare.get('kpis') or {}).get(kpi_key, 0.0)
            delta = cur - prev
            if abs(delta) < 100.0:
                continue
            ref = max(abs(cur), abs(prev), 1.0)
            if abs(delta) / ref < 0.01:
                continue
            account_rows = self._variance_top_accounts(
                parsed, type_map, kpi_types[kpi_key], prev_strict, kpi_key,
                cmp_dates, cur_strict=cur_strict,
            )
            partner_rows = self._variance_top_partners(
                parsed, kpi_types[kpi_key], cmp_dates,
            )
            delta_pct = (delta / abs(prev) * 100.0) if prev else None
            direction = 'up' if delta >= 0 else 'down'
            narrative = self._variance_narrative(
                kpi_key, kpi_labels[kpi_key], cur, prev, delta, delta_pct,
                account_rows, partner_rows,
            )
            results.append({
                'kpi': kpi_key,
                'label': kpi_labels[kpi_key],
                'current': round(cur, 2),
                'previous': round(prev, 2),
                'delta': round(delta, 2),
                'delta_pct': round(delta_pct, 1) if delta_pct is not None else None,
                'direction': direction,
                'accounts': account_rows,
                'partners': partner_rows,
                'narrative': narrative,
            })
        # Ordenar por magnitud absoluta del delta.
        results.sort(key=lambda r: abs(r['delta']), reverse=True)
        return results

    def _variance_top_accounts(self, parsed, type_map, types, prev_strict,
                               kpi_key, cmp_dates, limit=5, cur_strict=None):
        """Top de cuentas (por magnitud del delta) que componen el KPI."""
        if not types:
            return []
        type_set = set(types)
        type_ids = [aid for aid, t in type_map.items() if t in type_set]
        if not type_ids:
            return []
        # Reutilizamos el strict ya calculado por el caller si esta disponible;
        # solo recomputamos si no llego (compatibilidad con llamadas legacy).
        if cur_strict is None:
            cur_strict = self._per_account_sums(
                parsed, parsed['date_from'], parsed['date_to'],
            )
        # Signo del aporte al KPI por cuenta:
        # - revenue: ingreso es crédito (balance negativo); presentamos -balance.
        # - cogs / expenses: gasto/costo es débito (balance positivo); +balance.
        # - net_profit = -balance_P&L: una cuenta de ingreso (balance<0) suma
        #   utilidad; una cuenta de gasto (balance>0) la resta. En todos los
        #   casos el aporte a la utilidad es -balance, por eso sign=-1.
        def aid_sign(_aid):
            if kpi_key == 'revenue':
                return -1.0
            if kpi_key == 'net_profit':
                return -1.0
            return 1.0

        rows = []
        names = self._account_name_map(type_ids)
        for aid in type_ids:
            s = aid_sign(aid)
            cur_val = s * cur_strict.get(aid, {}).get('balance', 0.0)
            prev_val = s * prev_strict.get(aid, {}).get('balance', 0.0)
            delta = cur_val - prev_val
            if abs(delta) < 1.0:
                continue
            rows.append({
                'account_id': aid,
                'name': names.get(aid, str(aid)),
                'current': round(cur_val, 2),
                'previous': round(prev_val, 2),
                'delta': round(delta, 2),
            })
        rows.sort(key=lambda r: abs(r['delta']), reverse=True)
        rows = rows[:limit]
        total_abs = sum(abs(r['delta']) for r in rows) or 1.0
        for r in rows:
            r['share'] = round(abs(r['delta']) / total_abs * 100.0, 1)
        return rows

    def _variance_top_partners(self, parsed, types, cmp_dates, limit=3):
        """Top de terceros que aportaron al cambio (clientes/proveedores).

        Solo aplica cuando el KPI involucra cuentas con un tercero asociado
        en la mayoría de los apuntes (ingresos, cogs, gastos). Para Gastos
        suele haber un porcentaje sin tercero; en ese caso el delta puede
        quedar parcial (es un análisis indicativo, no una conciliación).
        """
        if not types:
            return []
        type_set = set(types)
        type_map = self._account_type_map(parsed['company'])
        type_ids = [aid for aid, t in type_map.items() if t in type_set]
        if not type_ids:
            return []
        df, dt = parsed['date_from'], parsed['date_to']
        pf, pt = cmp_dates

        def grouped(df_, dt_):
            domain = self._base_domain(parsed) + [
                ('date', '>=', df_), ('date', '<=', dt_),
                ('account_id', 'in', type_ids),
                ('partner_id', '!=', False),
            ]
            rows = self.env['account.move.line']._read_group(
                domain, groupby=['partner_id'], aggregates=['balance:sum'],
            )
            out = {}
            for partner, balance in rows:
                if partner:
                    out[partner.id] = float(balance or 0.0)
            return out

        cur_by_p = grouped(df, dt)
        prev_by_p = grouped(pf, pt)
        # Signo: en cuentas de ingreso, el balance es negativo (crédito).
        is_income = any(t in INCOME_TYPES for t in types)
        sign = -1.0 if is_income else 1.0

        deltas = {}
        for pid in set(cur_by_p) | set(prev_by_p):
            cur_v = sign * cur_by_p.get(pid, 0.0)
            prev_v = sign * prev_by_p.get(pid, 0.0)
            d = cur_v - prev_v
            if abs(d) >= 1.0:
                deltas[pid] = (cur_v, prev_v, d)
        ordered = sorted(deltas.items(), key=lambda kv: abs(kv[1][2]), reverse=True)[:limit]
        if not ordered:
            return []
        partner_ids = [pid for pid, _ in ordered]
        names = {}
        for p in self.env['res.partner'].sudo().browse(partner_ids).read(['display_name']):
            names[p['id']] = p['display_name']
        rows = []
        total_abs = sum(abs(d[2]) for _pid, d in ordered) or 1.0
        for pid, (cur_v, prev_v, d) in ordered:
            rows.append({
                'partner_id': pid,
                'name': names.get(pid, _('(Sin nombre)')),
                'current': round(cur_v, 2),
                'previous': round(prev_v, 2),
                'delta': round(d, 2),
                'share': round(abs(d) / total_abs * 100.0, 1),
            })
        return rows

    def _variance_narrative(self, kpi_key, label, cur, prev, delta, delta_pct,
                            account_rows, partner_rows):
        """Narrativa corta para mostrar al usuario y/o alimentar la IA."""
        symbol = self.env.company.currency_id.symbol or ''

        def m(v):
            return '%s%s' % (symbol, '{:,.0f}'.format(v or 0.0))

        parts = []
        pct_txt = ('%.1f%%' % delta_pct) if delta_pct is not None else _('vs. anterior')
        sign_pct = '+' if (delta or 0.0) >= 0 else ''
        parts.append(_('%s %s %s (%s%s).') % (
            label,
            _('aumentó') if delta >= 0 else _('bajó'),
            m(abs(delta)),
            sign_pct, pct_txt,
        ))
        if account_rows:
            top_acc = account_rows[0]
            parts.append(_('Cuenta con mayor impacto: %s (%s).') % (
                top_acc['name'], m(top_acc['delta']),
            ))
        if partner_rows:
            top_p = partner_rows[0]
            parts.append(_('Tercero con mayor impacto: %s (%s).') % (
                top_p['name'], m(top_p['delta']),
            ))
        return ' '.join(parts)

    # ------------------------------------------------------------------
    # Métodos por dominio (carga por sección)
    # ------------------------------------------------------------------
    def _build_compare(self, parsed, type_map):
        """Devuelve (compare, prev_strict) según el modo de comparación."""
        cmp_dates = self._comparison_dates(
            parsed['date_from'], parsed['date_to'], parsed['comparison'])
        if not cmp_dates:
            return None, None
        prev = self._kpis_for_period(parsed, type_map, cmp_dates[0], cmp_dates[1])
        compare = {
            'date_from': fields.Date.to_string(cmp_dates[0]),
            'date_to': fields.Date.to_string(cmp_dates[1]),
            'kpis': {k: v for k, v in prev.items() if not k.startswith('_')},
        }
        return compare, prev['_strict']

    @api.model
    def get_overview_data(self, filters):
        """Carga base del tablero (pestaña Resumen y datos compartidos).

        Es ligera respecto al payload completo: trae KPIs, comparativo, cartera
        (para la salud), tendencias, score explicable y metadatos, sin series
        completas ni rankings pesados.
        """
        parsed = self._parse_filters(filters)
        company = parsed['company']
        type_map = self._account_type_map(company)
        kpis = self._kpis_for_period(parsed, type_map, parsed['date_from'], parsed['date_to'])
        compare, _prev = self._build_compare(parsed, type_map)
        aging = self._aging(parsed)
        trends = self._trends(parsed, type_map)
        data_quality = self._data_quality(parsed)
        config_payload = self._build_config_payload(company)
        health = self._health_and_alerts(
            kpis, aging, config_payload['thresholds'],
            trends=trends, data_quality=data_quality,
        )
        kpi_public = {k: round(v, 2) for k, v in kpis.items() if not k.startswith('_')}
        return {
            'has_data': any(abs(v) > 0.009 for v in kpi_public.values()),
            'period': {
                'date_from': fields.Date.to_string(parsed['date_from']),
                'date_to': fields.Date.to_string(parsed['date_to']),
                'target_move': parsed['target_move'],
                'comparison': parsed['comparison'],
            },
            'currency': self._currency_payload(company.currency_id),
            'company_name': company.name,
            'kpis': kpi_public,
            'kpi_meta': self._kpi_meta(),
            'compare': compare,
            'aging': aging,
            'health': health,
            'trends': trends,
            'config': config_payload,
            'capabilities': self._capabilities(),
            'has_bi_reports': self._has_bi_reports(),
            'generated_at': fields.Datetime.now().isoformat(),
        }

    @api.model
    def get_profitability_data(self, filters):
        parsed = self._parse_filters(filters)
        type_map = self._account_type_map(parsed['company'])
        kpis = self._kpis_for_period(parsed, type_map, parsed['date_from'], parsed['date_to'])
        compare, prev_strict = self._build_compare(parsed, type_map)
        return {
            'kpis': {k: round(v, 2) for k, v in kpis.items() if not k.startswith('_')},
            'compare': compare,
            'monthly_series': self._monthly_series(parsed, type_map, parsed['date_from'], parsed['date_to']),
            'waterfall': self._waterfall(kpis),
            'expense_breakdown': self._expense_breakdown(kpis),
            'expense_ranking': self._expense_ranking(kpis, prev_strict),
        }

    @api.model
    def get_liquidity_data(self, filters):
        parsed = self._parse_filters(filters)
        type_map = self._account_type_map(parsed['company'])
        kpis = self._kpis_for_period(parsed, type_map, parsed['date_from'], parsed['date_to'])
        compare, _prev = self._build_compare(parsed, type_map)
        return {
            'kpis': {k: round(v, 2) for k, v in kpis.items() if not k.startswith('_')},
            'compare': compare,
        }

    @api.model
    def get_aging_data(self, filters):
        parsed = self._parse_filters(filters)
        aging = self._aging(parsed)
        type_map = self._account_type_map(parsed['company'])
        kpis = self._kpis_for_period(parsed, type_map, parsed['date_from'], parsed['date_to'])
        return {
            'aging': aging,
            'period_length': parsed['period_length'],
            'collection': self._collection_indicators(parsed, kpis, aging.get('receivable')),
            'payment': self._payment_indicators(parsed, kpis, aging.get('payable')),
            'partner_rankings': self._partner_rankings(parsed),
        }

    @api.model
    def get_diagnostics_data(self, filters):
        parsed = self._parse_filters(filters)
        company = parsed['company']
        type_map = self._account_type_map(company)
        kpis = self._kpis_for_period(parsed, type_map, parsed['date_from'], parsed['date_to'])
        aging = self._aging(parsed)
        collection = self._collection_indicators(parsed, kpis, aging.get('receivable'))
        payment = self._payment_indicators(parsed, kpis, aging.get('payable'))
        cashflow = self._cashflow(parsed, type_map)
        compare, prev_strict = self._build_compare(parsed, type_map)
        # Reusar el motor para entregar recomendaciones y centro de decisiones.
        trends = self._trends(parsed, type_map)
        data_quality = self._data_quality(parsed)
        config_payload = self._build_config_payload(company)
        health = self._health_and_alerts(
            kpis, aging, config_payload['thresholds'],
            trends=trends, data_quality=data_quality,
        )
        # Motor de variaciones (V20 Fase 1): explica los deltas vs período
        # comparativo descomponiendo por cuenta y tercero.
        variance = self._variance_analysis(parsed, type_map, kpis, compare, prev_strict)
        return {
            'analysis': self._financial_analysis(kpis, aging, collection, payment, cashflow, compare),
            'data_quality': data_quality,
            'closing_status': self._closing_status(parsed),
            'recommendations': health.get('recommendations') or [],
            'decisions': health.get('decisions') or [],
            'variance': variance,
        }

    @api.model
    def get_expense_ranking(self, filters):
        parsed = self._parse_filters(filters)
        type_map = self._account_type_map(parsed['company'])
        kpis = self._kpis_for_period(parsed, type_map, parsed['date_from'], parsed['date_to'])
        prev_strict = None
        cmp_dates = self._comparison_dates(parsed['date_from'], parsed['date_to'], parsed['comparison'])
        if cmp_dates:
            prev = self._kpis_for_period(parsed, type_map, cmp_dates[0], cmp_dates[1])
            prev_strict = prev['_strict']
        return self._expense_ranking(kpis, prev_strict)

    @api.model
    def get_partner_ranking(self, filters):
        parsed = self._parse_filters(filters)
        return self._partner_rankings(parsed)

    @api.model
    def get_cashflow_data(self, filters):
        parsed = self._parse_filters(filters)
        type_map = self._account_type_map(parsed['company'])
        return self._cashflow(parsed, type_map)

    @api.model
    def get_financial_analysis(self, filters):
        parsed = self._parse_filters(filters)
        type_map = self._account_type_map(parsed['company'])
        kpis = self._kpis_for_period(parsed, type_map, parsed['date_from'], parsed['date_to'])
        aging = self._aging(parsed)
        collection = self._collection_indicators(parsed, kpis, aging.get('receivable'))
        payment = self._payment_indicators(parsed, kpis, aging.get('payable'))
        cashflow = self._cashflow(parsed, type_map)
        return self._financial_analysis(kpis, aging, collection, payment, cashflow, None)

    @api.model
    def get_data_quality_alerts(self, filters):
        parsed = self._parse_filters(filters)
        return {
            'data_quality': self._data_quality(parsed),
            'closing_status': self._closing_status(parsed),
        }

    # ------------------------------------------------------------------
    # Planeación: presupuesto vs real, pronóstico y línea de tiempo
    # ------------------------------------------------------------------
    @api.model
    def get_planning_data(self, filters):
        """Datos de la pestaña Planeación para el año del rango de fechas.

        Devuelve:
        - ``budget``: matriz mensual real vs presupuesto por categoría + totales,
          % de avance y desviación.
        - ``forecast``: proyección a fin de año (ingresos/gastos/utilidad) según
          la tendencia del año en curso (regresión lineal simple).
        - ``timeline``: hitos financieros (cierres, meta anual, fecha de corte).
        - ``sim_base``: cifras base anualizadas para alimentar el simulador.
        """
        parsed = self._parse_filters(filters)
        company = parsed['company']
        year = parsed['date_to'].year
        type_map = self._account_type_map(company)

        budget = self.env['gn.financial.dashboard.budget'].get_or_create(company, year)
        budget_matrix = budget.monthly_matrix()
        actual_matrix = self._actual_monthly_matrix(parsed, type_map, year)

        budget_block = self._budget_vs_actual(budget_matrix, actual_matrix, parsed)
        forecast = self._forecast_year(actual_matrix, budget_matrix, parsed)
        timeline = self._planning_timeline(parsed, budget, forecast)
        return {
            'year': year,
            'currency': self._currency_payload(company.currency_id),
            'budget': budget_block,
            'forecast': forecast,
            'timeline': timeline,
            'sim_base': forecast['sim_base'],
            'can_edit_budget': self.env.user.has_group('account.group_account_manager'),
            'budget_action_id': self.env.ref(
                'gn_financial_dashboard.action_gn_fd_budget', raise_if_not_found=False
            ).id if self.env.ref(
                'gn_financial_dashboard.action_gn_fd_budget', raise_if_not_found=False
            ) else False,
        }

    def _actual_monthly_matrix(self, parsed, type_map, year):
        """Real por mes (12) y categoría: income/cogs/expenses para ``year``."""
        income_ids = [aid for aid, t in type_map.items() if t in INCOME_TYPES]
        cogs_ids = [aid for aid, t in type_map.items() if t in COGS_TYPES]
        expense_ids = [aid for aid, t in type_map.items() if t in EXPENSE_TYPES]
        from datetime import date
        y_from = date(year, 1, 1)
        y_to = date(year, 12, 31)
        base = self._base_domain(parsed) + [('date', '>=', y_from), ('date', '<=', y_to)]

        def grouped(ids, sign):
            if not ids:
                return [0.0] * 12
            rows = self.env['account.move.line']._read_group(
                base + [('account_id', 'in', ids)],
                groupby=['date:month'], aggregates=['balance:sum'],
            )
            out = [0.0] * 12
            for month, balance in rows:
                if month:
                    out[month.month - 1] = round(sign * float(balance or 0.0), 2)
            return out

        return {
            'income': grouped(income_ids, -1),
            'cogs': grouped(cogs_ids, 1),
            'expenses': grouped(expense_ids, 1),
        }

    def _budget_vs_actual(self, budget_matrix, actual_matrix, parsed):
        """Compara real vs presupuesto por categoría con % avance y desviación."""
        month_names = [
            _('Ene'), _('Feb'), _('Mar'), _('Abr'), _('May'), _('Jun'),
            _('Jul'), _('Ago'), _('Sep'), _('Oct'), _('Nov'), _('Dic'),
        ]
        # Mes hasta el cual hay datos reales (corte = mes de date_to).
        cutoff = parsed['date_to'].month

        categories = []
        for cat, label in (('income', _('Ingresos')), ('cogs', _('Costo de ventas')),
                           ('expenses', _('Gastos operativos'))):
            b = budget_matrix.get(cat, [0.0] * 12)
            a = actual_matrix.get(cat, [0.0] * 12)
            budget_total = round(sum(b), 2)
            actual_total = round(sum(a[:cutoff]), 2)
            budget_ytd = round(sum(b[:cutoff]), 2)
            progress = round((actual_total / budget_total * 100.0), 1) if budget_total else 0.0
            deviation = round(actual_total - budget_ytd, 2)
            deviation_pct = round((deviation / budget_ytd * 100.0), 1) if budget_ytd else 0.0
            categories.append({
                'key': cat,
                'label': label,
                'budget': b,
                'actual': a,
                'budget_total': budget_total,
                'actual_ytd': actual_total,
                'budget_ytd': budget_ytd,
                'progress': progress,
                'deviation': deviation,
                'deviation_pct': deviation_pct,
                # Para gastos/costo, desviación positiva (gastar de más) es mala.
                'favorable': (deviation >= 0) if cat == 'income' else (deviation <= 0),
            })

        # Utilidad neta (derivada).
        net_budget = [round(budget_matrix['income'][i] - budget_matrix['cogs'][i]
                            - budget_matrix['expenses'][i], 2) for i in range(12)]
        net_actual = [round(actual_matrix['income'][i] - actual_matrix['cogs'][i]
                            - actual_matrix['expenses'][i], 2) for i in range(12)]
        net_budget_total = round(sum(net_budget), 2)
        net_actual_ytd = round(sum(net_actual[:cutoff]), 2)
        net_budget_ytd = round(sum(net_budget[:cutoff]), 2)

        return {
            'labels': month_names,
            'cutoff': cutoff,
            'categories': categories,
            'net': {
                'budget': net_budget,
                'actual': net_actual,
                'budget_total': net_budget_total,
                'actual_ytd': net_actual_ytd,
                'budget_ytd': net_budget_ytd,
                'progress': round((net_actual_ytd / net_budget_total * 100.0), 1) if net_budget_total else 0.0,
                'deviation': round(net_actual_ytd - net_budget_ytd, 2),
            },
        }

    def _linear_project(self, series, periods_ahead):
        """Regresión lineal simple (mínimos cuadrados) para proyectar.

        ``series`` son los valores reales conocidos (uno por mes). Devuelve la
        suma proyectada de los ``periods_ahead`` meses siguientes.
        """
        n = len(series)
        if n == 0:
            return 0.0
        if n == 1:
            return series[0] * periods_ahead
        xs = list(range(n))
        sx = sum(xs)
        sy = sum(series)
        sxx = sum(x * x for x in xs)
        sxy = sum(x * y for x, y in zip(xs, series))
        denom = (n * sxx - sx * sx)
        if denom == 0:
            avg = sy / n
            return avg * periods_ahead
        slope = (n * sxy - sx * sy) / denom
        intercept = (sy - slope * sx) / n
        total = 0.0
        for k in range(n, n + periods_ahead):
            total += intercept + slope * k
        return total

    def _forecast_year(self, actual_matrix, budget_matrix, parsed):
        """Proyecta el cierre de año por tendencia de los meses con datos."""
        cutoff = parsed['date_to'].month
        remaining = 12 - cutoff
        result = {}
        for cat in ('income', 'cogs', 'expenses'):
            actual = actual_matrix[cat]
            known = actual[:cutoff]
            ytd = round(sum(known), 2)
            projected_rest = round(max(self._linear_project(known, remaining), 0.0), 2) if remaining else 0.0
            year_end = round(ytd + projected_rest, 2)
            budget_total = round(sum(budget_matrix.get(cat, [0.0] * 12)), 2)
            result[cat] = {
                'ytd': ytd,
                'projected_rest': projected_rest,
                'year_end': year_end,
                'budget_total': budget_total,
                'vs_budget': round(year_end - budget_total, 2),
                'attainment': round((year_end / budget_total * 100.0), 1) if budget_total else 0.0,
            }
        net_year_end = round(result['income']['year_end'] - result['cogs']['year_end']
                             - result['expenses']['year_end'], 2)
        net_budget = round(result['income']['budget_total'] - result['cogs']['budget_total']
                           - result['expenses']['budget_total'], 2)
        result['net'] = {
            'year_end': net_year_end,
            'budget_total': net_budget,
            'vs_budget': round(net_year_end - net_budget, 2),
            'attainment': round((net_year_end / net_budget * 100.0), 1) if net_budget else 0.0,
        }
        result['cutoff'] = cutoff
        # Base anualizada para el simulador (proyección a fin de año).
        result['sim_base'] = {
            'income': result['income']['year_end'],
            'cogs': result['cogs']['year_end'],
            'expenses': result['expenses']['year_end'],
        }
        return result

    def _planning_timeline(self, parsed, budget, forecast):
        """Hitos financieros del año: cierres mensuales, corte y meta anual."""
        from datetime import date
        year = parsed['date_to'].year
        cutoff = parsed['date_to'].month
        events = []
        month_names = [
            _('Enero'), _('Febrero'), _('Marzo'), _('Abril'), _('Mayo'), _('Junio'),
            _('Julio'), _('Agosto'), _('Septiembre'), _('Octubre'), _('Noviembre'), _('Diciembre'),
        ]
        # Cierres mensuales (pasados = done, futuros = pending).
        for m in range(1, 13):
            events.append({
                'date': fields.Date.to_string(date(year, m, 1)),
                'title': _('Cierre %s') % month_names[m - 1],
                'type': 'closing',
                'status': 'done' if m <= cutoff else 'pending',
            })
        # Corte actual.
        events.append({
            'date': fields.Date.to_string(parsed['date_to']),
            'title': _('Corte de análisis'),
            'type': 'milestone',
            'status': 'current',
        })
        # Meta anual de utilidad.
        events.append({
            'date': fields.Date.to_string(date(year, 12, 31)),
            'title': _('Meta de utilidad: %s') % self._fmt_company_amount(
                parsed['company'], budget.total_net),
            'type': 'goal',
            'status': 'forecast',
            'forecast': forecast['net']['year_end'],
            'attainment': forecast['net']['attainment'],
        })
        events.sort(key=lambda e: e['date'])
        return events

    def _fmt_company_amount(self, company, amount):
        cur = company.currency_id
        return '%s%s' % (cur.symbol or '', '{:,.0f}'.format(amount or 0.0))

    # ------------------------------------------------------------------
    # Vigilancia: comparación multi-año, benchmark, calendario y alertas
    # ------------------------------------------------------------------
    @api.model
    def get_watch_data(self, filters):
        """Datos de la pestaña de Comparativos y Vigilancia.

        Reúne en una sola llamada:
        - ``multiyear``: ingresos/gastos/utilidad de los últimos N años.
        - ``benchmark``: KPIs clave por compañía (la actual + sus hijas).
        - ``calendar``: próximos vencimientos por cobrar/pagar y cierres.
        - ``alerts``: centro de alertas inteligentes consolidado.
        """
        parsed = self._parse_filters(filters)
        return {
            'currency': self._currency_payload(parsed['company'].currency_id),
            'multiyear': self._multiyear(parsed),
            'benchmark': self._benchmark(parsed),
            'calendar': self._financial_calendar(parsed),
            'alerts': self._alert_center(parsed),
        }

    def _multiyear(self, parsed, years=4):
        """Ingresos, gastos y utilidad de los últimos ``years`` años fiscales."""
        from datetime import date
        type_map = self._account_type_map(parsed['company'])
        end_year = parsed['date_to'].year
        labels, income, expense, net, margin = [], [], [], [], []
        for y in range(end_year - years + 1, end_year + 1):
            y_from = date(y, 1, 1)
            # Para el año en curso, recortamos al corte (date_to) para comparar
            # manzanas con manzanas (YTD), salvo años pasados (año completo).
            y_to = parsed['date_to'] if y == end_year else date(y, 12, 31)
            sub = dict(parsed)
            kpis = self._kpis_for_period(sub, type_map, y_from, y_to)
            labels.append(str(y))
            income.append(round(kpis['revenue'], 2))
            expense.append(round(kpis['cogs'] + kpis['expenses'], 2))
            net.append(round(kpis['net_profit'], 2))
            margin.append(round(kpis['net_margin'], 1))
        # Crecimiento interanual de ingresos y utilidad (último vs anterior).
        def growth(seq):
            if len(seq) < 2 or not seq[-2]:
                return 0.0
            return round((seq[-1] - seq[-2]) / abs(seq[-2]) * 100.0, 1)
        return {
            'labels': labels,
            'income': income,
            'expense': expense,
            'net': net,
            'margin': margin,
            'current_year_partial': True,
            'growth': {
                'income': growth(income),
                'net': growth(net),
            },
        }

    def _benchmark(self, parsed):
        """KPIs clave por compañía (actual + hijas accesibles)."""
        root = parsed['company']
        companies = self.env['res.company'].search([('id', 'child_of', root.id)])
        # Solo compañías a las que el usuario tiene acceso.
        companies = companies & self.env.user.company_ids
        if not companies:
            companies = root
        rows = []
        for comp in companies:
            sub = dict(parsed)
            sub['company'] = comp
            type_map = self._account_type_map(comp)
            kpis = self._kpis_for_period(sub, type_map, parsed['date_from'], parsed['date_to'])
            rows.append({
                'company_id': comp.id,
                'name': comp.name,
                'revenue': round(kpis['revenue'], 2),
                'net_profit': round(kpis['net_profit'], 2),
                'net_margin': round(kpis['net_margin'], 1),
                'current_ratio': round(kpis['current_ratio'], 2),
                'closing_bank': round(kpis['closing_bank'], 2),
                'receivables': round(kpis['receivables'], 2),
                'is_current': comp.id == root.id,
            })
        rows.sort(key=lambda r: r['net_profit'], reverse=True)
        # Marcamos el mejor/peor margen para resaltar en la UI.
        if rows:
            best = max(rows, key=lambda r: r['net_margin'])
            worst = min(rows, key=lambda r: r['net_margin'])
            for r in rows:
                r['rank_margin'] = ('best' if r is best else
                                    'worst' if r is worst else 'mid')
        return {
            'multi': len(rows) > 1,
            'rows': rows,
        }

    def _financial_calendar(self, parsed, horizon_days=60, limit=40):
        """Próximos vencimientos (cobrar/pagar) y cierres dentro del horizonte."""
        on_date = parsed['date_to']
        horizon = on_date + timedelta(days=horizon_days)
        states = ('posted',) if parsed['target_move'] == 'posted' else ('posted', 'draft')
        type_ids = [
            aid for aid, t in self._account_type_map(parsed['company']).items()
            if t in RECEIVABLE_TYPES or t in PAYABLE_TYPES
        ]
        events = []
        if type_ids:
            domain = [
                ('company_id', 'child_of', parsed['company'].id),
                ('parent_state', 'in', states),
                ('account_id', 'in', type_ids),
                ('amount_residual', '!=', 0.0),
                ('date_maturity', '>=', on_date),
                ('date_maturity', '<=', horizon),
            ]
            if parsed['journal_ids']:
                domain.append(('journal_id', 'in', parsed['journal_ids']))
            type_map = self._account_type_map(parsed['company'])
            rows = self.env['account.move.line']._read_group(
                domain, groupby=['date_maturity:day', 'account_id'],
                aggregates=['amount_residual:sum'],
            )
            agg = {}
            for mday, account, residual in rows:
                if not mday:
                    continue
                key = fields.Date.to_string(mday)
                side = 'receivable' if type_map.get(account.id) in RECEIVABLE_TYPES else 'payable'
                slot = agg.setdefault((key, side), 0.0)
                agg[(key, side)] = slot + float(residual or 0.0)
            for (key, side), amount in agg.items():
                events.append({
                    'date': key,
                    'type': side,
                    'amount': round(abs(amount), 2),
                    'title': (_('Cobros que vencen') if side == 'receivable'
                              else _('Pagos que vencen')),
                })
        events.sort(key=lambda e: (e['date'], e['type']))
        events = events[:limit]
        # Resumen del horizonte.
        total_in = round(sum(e['amount'] for e in events if e['type'] == 'receivable'), 2)
        total_out = round(sum(e['amount'] for e in events if e['type'] == 'payable'), 2)
        return {
            'horizon_days': horizon_days,
            'from': fields.Date.to_string(on_date),
            'to': fields.Date.to_string(horizon),
            'events': events,
            'total_receivable': total_in,
            'total_payable': total_out,
            'net': round(total_in - total_out, 2),
        }

    def _alert_center(self, parsed):
        """Consolida alertas de salud, cartera, calidad, presupuesto y caja."""
        company = parsed['company']
        type_map = self._account_type_map(company)
        kpis = self._kpis_for_period(parsed, type_map, parsed['date_from'], parsed['date_to'])
        aging = self._aging(parsed)
        data_quality = self._data_quality(parsed)
        trends = self._trends(parsed, type_map)
        config_payload = self._build_config_payload(company)
        health = self._health_and_alerts(
            kpis, aging, config_payload['thresholds'],
            trends=trends, data_quality=data_quality,
        )

        alerts = []

        def add(severity, category, title, detail, value=None):
            alerts.append({
                'severity': severity,  # critical | warning | info
                'category': category,
                'title': title,
                'detail': detail or '',
                'value': value,
            })

        # 1) Salud financiera global.
        level = health.get('level')
        if level in ('risk', 'warning'):
            add('critical' if level == 'risk' else 'warning', _('Salud'),
                _('Salud financiera: %s') % (health.get('label') or ''),
                _('Puntaje global %s/100.') % health.get('score', 0),
                health.get('score'))

        # 2) Recomendaciones del motor (alta prioridad → warning/critical).
        for reco in (health.get('recommendations') or [])[:5]:
            prio = reco.get('priority')
            sev = 'critical' if prio == 'high' else 'warning' if prio == 'medium' else 'info'
            add(sev, _('Acción'), reco.get('title') or _('Recomendación'),
                reco.get('expected_impact') or reco.get('description') or '')

        # 3) Cartera vencida +120.
        recv = aging.get('receivable') or {}
        if recv.get('total') and recv.get('over_120'):
            pct = recv['over_120'] / recv['total'] * 100.0 if recv['total'] else 0.0
            if pct >= config_payload['thresholds'].get('max_over_120_pct', 15.0):
                add('warning', _('Cartera'),
                    _('Cartera +120 días elevada'),
                    _('%.1f%% de la cartera por cobrar supera 120 días.') % pct,
                    round(recv['over_120'], 2))

        # 4) Caja negativa / déficit de flujo.
        if kpis.get('closing_bank', 0.0) < 0:
            add('critical', _('Liquidez'), _('Saldo bancario negativo'),
                _('El saldo de bancos/caja al corte es negativo.'),
                round(kpis['closing_bank'], 2))
        if kpis.get('cash_surplus', 0.0) < 0:
            add('warning', _('Liquidez'), _('Flujo de caja negativo'),
                _('Las salidas de efectivo superan las entradas del período.'),
                round(kpis['cash_surplus'], 2))

        # 5) Calidad de datos (cada check listado ya representa un problema).
        dq_checks = (data_quality or {}).get('checks') or []
        for chk in dq_checks:
            sev = 'critical' if chk.get('severity') == 'danger' else 'warning'
            add(sev, _('Calidad de datos'),
                chk.get('title') or _('Revisión de datos'),
                chk.get('message') or '')

        # 6) Presupuesto: desviación desfavorable significativa (si existe).
        budget = self.env['gn.financial.dashboard.budget'].sudo().search([
            ('company_id', '=', company.id), ('year', '=', parsed['date_to'].year),
        ], limit=1)
        if budget and budget.total_net:
            actual = self._actual_monthly_matrix(parsed, type_map, parsed['date_to'].year)
            cutoff = parsed['date_to'].month
            net_actual = sum(actual['income'][i] - actual['cogs'][i] - actual['expenses'][i]
                             for i in range(cutoff))
            bmatrix = budget.monthly_matrix()
            net_budget_ytd = sum(bmatrix['income'][i] - bmatrix['cogs'][i] - bmatrix['expenses'][i]
                                 for i in range(cutoff))
            if net_budget_ytd and net_actual < net_budget_ytd * 0.9:
                gap = round(net_budget_ytd - net_actual, 2)
                add('warning', _('Presupuesto'),
                    _('Utilidad por debajo de la meta'),
                    _('La utilidad acumulada está %s por debajo de la meta YTD.')
                    % self._fmt_company_amount(company, gap), gap)

        # 7) Vencimientos próximos (resumen del calendario).
        cal = self._financial_calendar(parsed)
        if cal['net'] < 0:
            add('info', _('Calendario'),
                _('Presión de pagos próxima'),
                _('En los próximos %s días los pagos superan a los cobros.')
                % cal['horizon_days'], cal['net'])

        order = {'critical': 0, 'warning': 1, 'info': 2}
        alerts.sort(key=lambda a: order.get(a['severity'], 3))
        counts = {
            'critical': sum(1 for a in alerts if a['severity'] == 'critical'),
            'warning': sum(1 for a in alerts if a['severity'] == 'warning'),
            'info': sum(1 for a in alerts if a['severity'] == 'info'),
        }
        return {'alerts': alerts, 'counts': counts, 'total': len(alerts)}

    @api.model
    def get_watch_chart_meta(self):
        """Meta de ayuda para los paneles de la pestaña de vigilancia."""
        return {
            'multiyear': {
                'title': _('Comparación multi-año'),
                'desc': _('Ingresos, gastos y utilidad de los últimos años.'),
                'hint': _('El año en curso es parcial (hasta la fecha de corte).'),
            },
        }

    # ------------------------------------------------------------------
    # Vista ejecutiva y narrativa (preparación para IA)
    # ------------------------------------------------------------------
    @api.model
    def get_executive_data(self, filters):
        """Payload condensado para la vista ejecutiva (resumen de una ojeada).

        Reúne salud, KPIs clave, principales alertas, pronóstico y mini serie
        multi-año, e incluye una narrativa en lenguaje natural lista para
        mostrarse o, en el futuro, ser generada por un proveedor de IA.
        """
        parsed = self._parse_filters(filters)
        company = parsed['company']
        type_map = self._account_type_map(company)
        kpis = self._kpis_for_period(parsed, type_map, parsed['date_from'], parsed['date_to'])
        compare, prev_strict = self._build_compare(parsed, type_map)
        aging = self._aging(parsed)
        trends = self._trends(parsed, type_map)
        data_quality = self._data_quality(parsed)
        config_payload = self._build_config_payload(company)
        health = self._health_and_alerts(
            kpis, aging, config_payload['thresholds'],
            trends=trends, data_quality=data_quality,
        )
        alerts = self._alert_center(parsed)
        multiyear = self._multiyear(parsed)
        variance = self._variance_analysis(parsed, type_map, kpis, compare, prev_strict)
        # Pronóstico reutilizando el motor de planeación.
        year = parsed['date_to'].year
        budget = self.env['gn.financial.dashboard.budget'].get_or_create(company, year)
        actual_matrix = self._actual_monthly_matrix(parsed, type_map, year)
        forecast = self._forecast_year(actual_matrix, budget.monthly_matrix(), parsed)

        kpi_public = {k: round(v, 2) for k, v in kpis.items() if not k.startswith('_')}
        context = self._executive_context(
            company, parsed, kpi_public, compare, health, alerts,
            multiyear, forecast, variance,
        )
        narrative = self._ai_generate(context)
        return {
            'currency': self._currency_payload(company.currency_id),
            'company_name': company.name,
            'period': {
                'date_from': fields.Date.to_string(parsed['date_from']),
                'date_to': fields.Date.to_string(parsed['date_to']),
            },
            'health': {
                'score': health.get('score'),
                'level': health.get('level'),
                'label': health.get('label'),
            },
            'kpis': kpi_public,
            'compare': compare,
            'alerts': {
                'counts': alerts['counts'],
                'top': alerts['alerts'][:5],
            },
            'multiyear': multiyear,
            'forecast': {
                'net_year_end': forecast['net']['year_end'],
                'net_attainment': forecast['net']['attainment'],
                'income_year_end': forecast['income']['year_end'],
            },
            'narrative': narrative,
            'ai': context['ai_meta'],
        }

    def _executive_context(self, company, parsed, kpis, compare, health,
                           alerts, multiyear, forecast, variance=None):
        """Construye el contexto estructurado que alimenta la narrativa/IA.

        Devolver este diccionario por separado facilita, en el futuro, enviarlo
        como *prompt* estructurado a un proveedor de IA sin recalcular nada.
        ``variance`` (opcional) es la salida de ``_variance_analysis``: causas
        principales de los deltas vs período comparativo.
        """
        cur = company.currency_id

        def delta_pct(key):
            if not compare:
                return None
            prev = (compare.get('kpis') or {}).get(key)
            cur_v = kpis.get(key)
            if prev in (None, 0) or cur_v is None:
                return None
            return round((cur_v - prev) / abs(prev) * 100.0, 1)

        return {
            'company': company.name,
            'currency': cur.symbol or cur.name or '',
            'period': {
                'from': fields.Date.to_string(parsed['date_from']),
                'to': fields.Date.to_string(parsed['date_to']),
            },
            'kpis': kpis,
            'deltas': {
                'revenue': delta_pct('revenue'),
                'net_profit': delta_pct('net_profit'),
                'expenses': delta_pct('expenses'),
            },
            'health': {
                'score': health.get('score'),
                'level': health.get('level'),
                'label': health.get('label'),
            },
            'alerts': {
                'counts': alerts['counts'],
                'titles': [a['title'] for a in alerts['alerts'][:3]],
            },
            'forecast': {
                'net_year_end': forecast['net']['year_end'],
                'net_attainment': forecast['net']['attainment'],
            },
            'multiyear': {
                'years': multiyear['labels'],
                'net': multiyear['net'],
                'growth': multiyear['growth'],
            },
            # Top 2 causas principales (con su narrativa corta) para la IA.
            'variance': [
                {
                    'kpi': v['kpi'],
                    'label': v['label'],
                    'delta': v['delta'],
                    'delta_pct': v['delta_pct'],
                    'narrative': v['narrative'],
                    'top_account': (v['accounts'][0]['name']
                                    if v.get('accounts') else None),
                    'top_partner': (v['partners'][0]['name']
                                    if v.get('partners') else None),
                }
                for v in (variance or [])[:2]
            ],
            'ai_meta': {
                'provider': 'rule_based',
                'generated_by': 'gn_financial_dashboard',
            },
        }

    def _ai_generate(self, context):
        """Genera la narrativa a partir del contexto estructurado.

        Punto de extensión para IA: por defecto usa un generador determinista
        basado en reglas (``_build_narrative``). Un módulo que dependa de este
        puede sobreescribir este método para llamar a un LLM usando ``context``
        como *prompt* estructurado, devolviendo la misma estructura
        ``{'summary': str, 'bullets': [str], 'source': str}``.
        """
        return self._build_narrative(context)

    def _build_narrative(self, context):
        """Narrativa determinista (es) a partir del contexto financiero."""
        cur = context['currency']
        k = context['kpis']
        d = context['deltas']

        def money(v):
            return '%s%s' % (cur, '{:,.0f}'.format(v or 0.0))

        def trend_word(pct):
            if pct is None:
                return ''
            if pct > 1:
                return _(' (+%.1f%% vs período anterior)') % pct
            if pct < -1:
                return _(' (%.1f%% vs período anterior)') % pct
            return _(' (estable vs período anterior)')

        bullets = []
        # Rentabilidad.
        net = k.get('net_profit', 0.0)
        margin = k.get('net_margin', 0.0)
        if net >= 0:
            bullets.append(_('Utilidad neta de %(net)s con un margen del %(m).1f%%%(t)s.',
                             net=money(net), m=margin, t=trend_word(d.get('net_profit'))))
        else:
            bullets.append(_('Pérdida neta de %(net)s; revisar costos y gastos%(t)s.',
                             net=money(abs(net)), t=trend_word(d.get('net_profit'))))
        # Ingresos.
        bullets.append(_('Ingresos por %(rev)s%(t)s.',
                        rev=money(k.get('revenue', 0.0)), t=trend_word(d.get('revenue'))))
        # Liquidez.
        cr = k.get('current_ratio', 0.0)
        bank = k.get('closing_bank', 0.0)
        if cr:
            liq = _('cómoda') if cr >= 1.5 else _('ajustada') if cr >= 1 else _('crítica')
            bullets.append(_('Liquidez %(liq)s (razón corriente %(cr).2f); saldo en bancos %(bank)s.',
                             liq=liq, cr=cr, bank=money(bank)))
        # Cartera.
        recv = k.get('receivables', 0.0)
        if recv:
            bullets.append(_('Cartera por cobrar de %(recv)s pendiente de gestión.',
                             recv=money(recv)))
        # Pronóstico.
        fc = context['forecast']
        if fc.get('net_attainment'):
            bullets.append(_('Proyección de utilidad a fin de año: %(ye)s (%(att).0f%% de la meta).',
                             ye=money(fc['net_year_end']), att=fc['net_attainment']))
        # Causa principal del delta (motor de variaciones).
        for v in context.get('variance') or []:
            if v.get('narrative'):
                bullets.append(v['narrative'])

        # Encabezado según salud.
        health = context['health']
        level = health.get('level')
        head_map = {
            'excellent': _('La situación financiera es excelente.'),
            'good': _('La situación financiera es sólida.'),
            'warning': _('La situación financiera requiere atención.'),
            'risk': _('La situación financiera es de riesgo y exige acción inmediata.'),
        }
        head = head_map.get(level, _('Resumen financiero del período.'))
        counts = context['alerts']['counts']
        if counts.get('critical'):
            head += _(' Hay %d alerta(s) crítica(s) que atender.') % counts['critical']

        summary = '%s %s' % (head, ' '.join(bullets))
        return {
            'summary': summary,
            'bullets': bullets,
            'headline': head,
            'source': context['ai_meta']['provider'],
        }

    # ------------------------------------------------------------------
    # Orquestación
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_data(self, filters):
        parsed = self._parse_filters(filters)
        company = parsed['company']
        type_map = self._account_type_map(company)

        kpis = self._kpis_for_period(parsed, type_map, parsed['date_from'], parsed['date_to'])

        compare = None
        prev_strict = None
        cmp_dates = self._comparison_dates(parsed['date_from'], parsed['date_to'], parsed['comparison'])
        if cmp_dates:
            prev = self._kpis_for_period(parsed, type_map, cmp_dates[0], cmp_dates[1])
            prev_strict = prev['_strict']
            compare = {
                'date_from': fields.Date.to_string(cmp_dates[0]),
                'date_to': fields.Date.to_string(cmp_dates[1]),
                'kpis': {k: v for k, v in prev.items() if not k.startswith('_')},
            }

        aging = self._aging(parsed)
        trends = self._trends(parsed, type_map)
        data_quality = self._data_quality(parsed)
        config_payload = self._build_config_payload(company)
        health = self._health_and_alerts(
            kpis, aging, config_payload['thresholds'],
            trends=trends, data_quality=data_quality,
        )
        partner_rankings = self._partner_rankings(parsed)
        expense_ranking = self._expense_ranking(kpis, prev_strict)
        collection = self._collection_indicators(parsed, kpis, aging.get('receivable'))
        payment = self._payment_indicators(parsed, kpis, aging.get('payable'))
        cashflow = self._cashflow(parsed, type_map)
        analysis = self._financial_analysis(kpis, aging, collection, payment, cashflow, compare)
        closing_status = self._closing_status(parsed)

        kpi_public = {k: round(v, 2) for k, v in kpis.items() if not k.startswith('_')}
        return {
            'has_data': any(abs(v) > 0.009 for v in kpi_public.values()),
            'period': {
                'date_from': fields.Date.to_string(parsed['date_from']),
                'date_to': fields.Date.to_string(parsed['date_to']),
                'target_move': parsed['target_move'],
                'comparison': parsed['comparison'],
            },
            'currency': self._currency_payload(company.currency_id),
            'company_name': company.name,
            'kpis': kpi_public,
            'kpi_meta': self._kpi_meta(),
            'compare': compare,
            'monthly_series': self._monthly_series(parsed, type_map, parsed['date_from'], parsed['date_to']),
            'waterfall': self._waterfall(kpis),
            'expense_breakdown': self._expense_breakdown(kpis),
            'expense_ranking': expense_ranking,
            'partner_rankings': partner_rankings,
            'collection': collection,
            'payment': payment,
            'cashflow': cashflow,
            'analysis': analysis,
            'data_quality': data_quality,
            'closing_status': closing_status,
            'aging': aging,
            'health': health,
            'trends': trends,
            'recommendations': health.get('recommendations') or [],
            'decisions': health.get('decisions') or [],
            'config': config_payload,
            'capabilities': self._capabilities(),
            'has_bi_reports': self._has_bi_reports(),
            'generated_at': fields.Datetime.now().isoformat(),
        }

    # ------------------------------------------------------------------
    # Drill-down a los reportes del módulo BI
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Detalle por cuenta (drill-down de un KPI)
    # ------------------------------------------------------------------
    # KPI -> tipos de cuenta que lo componen (para el detalle).
    KPI_ACCOUNT_TYPES = {
        'revenue': INCOME_TYPES,
        'cogs': COGS_TYPES,
        'gross_profit': INCOME_TYPES + COGS_TYPES,
        'expenses': EXPENSE_TYPES,
        'net_profit': INCOME_TYPES + COGS_TYPES + EXPENSE_TYPES,
        'cash_surplus': CASH_TYPES,
        'closing_bank': CASH_TYPES,
        'receivables': RECEIVABLE_TYPES,
        'payables': PAYABLE_TYPES,
        'working_capital': CURRENT_ASSET_TYPES + CURRENT_LIABILITY_TYPES,
        'total_assets': ASSET_TYPES,
        'net_assets': ASSET_TYPES + LIABILITY_TYPES,
        # Ratios derivados: drill al componente principal (vía tipos).
        'ebit': INCOME_TYPES + COGS_TYPES + EXPENSE_TYPES,
        'ebitda': INCOME_TYPES + COGS_TYPES + EXPENSE_TYPES,
        'operating_margin': INCOME_TYPES + EXPENSE_TYPES,
        'ebitda_margin': INCOME_TYPES + EXPENSE_TYPES,
        'roa': INCOME_TYPES + COGS_TYPES + EXPENSE_TYPES,
        'roe': INCOME_TYPES + COGS_TYPES + EXPENSE_TYPES,
        'assets_turnover': INCOME_TYPES,
        'ar_turnover': RECEIVABLE_TYPES,
        'ap_turnover': PAYABLE_TYPES,
        'leverage_ratio': ASSET_TYPES,
    }
    # Tipos cuyo saldo se muestra invertido para lectura "natural".
    _INVERT_DISPLAY = set(
        INCOME_TYPES + PAYABLE_TYPES + (
            'liability_credit_card', 'liability_current',
            'liability_non_current', 'equity', 'equity_unaffected',
        )
    )

    def _display_sign(self, account_type):
        return -1.0 if account_type in self._INVERT_DISPLAY else 1.0

    @api.model
    def get_account_detail(self, filters, kpi_key=None):
        """Detalle por cuenta del grupo de un KPI, respetando filtros.

        Devuelve por cuenta: código, nombre, tipo, saldo del período, saldo del
        período anterior, variación absoluta y %, y compañía.
        """
        parsed = self._parse_filters(filters)
        type_map = self._account_type_map(parsed['company'])
        types = set(self.KPI_ACCOUNT_TYPES.get(kpi_key, ()))

        # Cuentas de balance: saldo acumulado; cuentas de resultado: del período.
        balance_kpi = kpi_key in ('closing_bank', 'receivables', 'payables',
                                  'working_capital', 'total_assets', 'net_assets')
        cur = self._per_account_sums(parsed, parsed['date_from'], parsed['date_to'],
                                     from_beginning=balance_kpi)
        prev = {}
        cmp_dates = self._comparison_dates(parsed['date_from'], parsed['date_to'], parsed['comparison'])
        if cmp_dates:
            prev = self._per_account_sums(parsed, cmp_dates[0], cmp_dates[1],
                                          from_beginning=balance_kpi)

        account_ids = [aid for aid in cur if type_map.get(aid) in types] if types else list(cur)
        names = self._account_name_map(account_ids)
        # Códigos y nombres por separado para columnas.
        code_name = {}
        if account_ids:
            for r in self.env['account.account'].browse(account_ids).read(['code', 'name']):
                code_name[r['id']] = (r.get('code') or '', r.get('name') or '')

        rows = []
        for aid in account_ids:
            atype = type_map.get(aid)
            sign = self._display_sign(atype)
            bal = sign * cur.get(aid, {}).get('balance', 0.0)
            pbal = sign * prev.get(aid, {}).get('balance', 0.0)
            if abs(bal) < 0.009 and abs(pbal) < 0.009:
                continue
            delta = bal - pbal
            delta_pct = (delta / abs(pbal) * 100.0) if pbal else None
            code, name = code_name.get(aid, ('', ''))
            rows.append({
                'account_id': aid,
                'code': code,
                'name': name,
                'account_type': atype,
                'balance': round(bal, 2),
                'prev_balance': round(pbal, 2),
                'delta': round(delta, 2),
                'delta_pct': round(delta_pct, 1) if delta_pct is not None else None,
                'company': parsed['company'].name,
            })
        rows.sort(key=lambda r: abs(r['balance']), reverse=True)
        return {
            'rows': rows,
            'currency': self._currency_payload(parsed['company'].currency_id),
            'has_compare': bool(cmp_dates),
            'kpi_key': kpi_key,
        }

    @api.model
    def open_move_lines(self, payload):
        """Abre la vista de apuntes contables filtrada (drill-down).

        Solo para gestores contables. Respeta compañía, fechas, diarios y
        estado de asiento de los filtros activos. Soporta varios ``drill_type``:

        - ``expense``/``account``: por una cuenta concreta (con ``account_id``).
        - ``receivable_partner``/``payable_partner``: cartera abierta por tercero.
        - ``account_type``: por uno o varios ``account_type`` (clic en cascada).
        - ``account_type_month``: cuenta(s) de un tipo en un mes concreto
          (clic en barra mensual, con ``month`` = ``YYYY-MM``).
        - ``aging_bucket``: cuentas por cobrar/pagar de un tramo (``bucket`` 0..5)
          combinado con ``side`` (``receivable``|``payable``).
        - ``cash_month``: movimientos de efectivo en un mes (flujo de caja).
        """
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_('Necesita permisos de gestor contable para ver el detalle.'))
        parsed = self._parse_filters(payload)
        drill_type = payload.get('drill_type')
        domain = self._base_domain(parsed)
        name = _('Apuntes contables')
        if drill_type in ('expense', 'account'):
            account_id = payload.get('account_id')
            domain += [('date', '>=', parsed['date_from']), ('date', '<=', parsed['date_to'])]
            if account_id:
                domain.append(('account_id', '=', account_id))
            name = _('Detalle de gasto') if drill_type == 'expense' else _('Detalle de cuenta')
        elif drill_type in ('receivable_partner', 'payable_partner'):
            types = RECEIVABLE_TYPES if drill_type == 'receivable_partner' else PAYABLE_TYPES
            ids = self._aging_resid_line_ids(
                parsed, list(types), partner_id=payload.get('partner_id'))
            domain = [('id', 'in', ids or [0])]
            name = _('Cartera del tercero')
        elif drill_type == 'account_type':
            type_ids = self._account_ids_for_types(parsed, payload.get('account_types') or [])
            domain += [
                ('account_id', 'in', type_ids or [0]),
                ('date', '>=', parsed['date_from']),
                ('date', '<=', parsed['date_to']),
            ]
            name = payload.get('label') or _('Detalle del componente')
        elif drill_type == 'account_type_month':
            type_ids = self._account_ids_for_types(parsed, payload.get('account_types') or [])
            month_from, month_to = self._month_bounds(payload.get('month'), parsed)
            domain += [
                ('account_id', 'in', type_ids or [0]),
                ('date', '>=', month_from), ('date', '<=', month_to),
            ]
            name = payload.get('label') or _('Detalle del mes')
        elif drill_type == 'aging_bucket':
            side = payload.get('side') or 'receivable'
            types = RECEIVABLE_TYPES if side == 'receivable' else PAYABLE_TYPES
            bucket = int(payload.get('bucket') or 0)
            from_days, to_days = self._aging_bucket_bounds(
                bucket, parsed['period_length'])
            cand_ids = self._aging_resid_line_ids(parsed, list(types))
            ids = self._filter_lines_by_aging(
                [('id', 'in', cand_ids or [0])], parsed['date_to'], from_days, to_days)
            domain = [('id', 'in', ids or [0])]
            name = payload.get('label') or _('Tramo de cartera')
        elif drill_type == 'cash_month':
            type_ids = self._account_ids_for_types(parsed, list(CASH_TYPES))
            month_from, month_to = self._month_bounds(payload.get('month'), parsed)
            domain += [
                ('account_id', 'in', type_ids or [0]),
                ('date', '>=', month_from), ('date', '<=', month_to),
            ]
            name = payload.get('label') or _('Movimientos de efectivo')
        elif drill_type == 'product':
            # Drill-down de un producto (V20 Fase 3 #8): apuntes de ingreso o
            # COGS de un producto en el rango activo. ``side`` define cuál.
            type_map = self._account_type_map(parsed['company'])
            side = payload.get('side') or 'revenue'
            if side == 'cogs':
                types = ('expense_direct_cost',)
            elif side == 'expense':
                types = EXPENSE_TYPES + COGS_TYPES
            else:
                types = INCOME_TYPES
            type_ids = [aid for aid, t in type_map.items() if t in types]
            product_id = int(payload.get('product_id') or 0)
            domain += [
                ('account_id', 'in', type_ids or [0]),
                ('product_id', '=', product_id),
                ('date', '>=', parsed['date_from']),
                ('date', '<=', parsed['date_to']),
            ]
            name = payload.get('label') or _('Movimientos del producto')
        elif drill_type == 'partner_revenue':
            # Apuntes de ingreso de un cliente en el rango.
            type_map = self._account_type_map(parsed['company'])
            type_ids = [aid for aid, t in type_map.items() if t in INCOME_TYPES]
            partner_id = int(payload.get('partner_id') or 0)
            domain += [
                ('account_id', 'in', type_ids or [0]),
                ('partner_id', '=', partner_id),
                ('date', '>=', parsed['date_from']),
                ('date', '<=', parsed['date_to']),
            ]
            name = payload.get('label') or _('Ingresos del cliente')
        elif drill_type == 'partner_purchases':
            # Apuntes de compra/gasto de un proveedor en el rango.
            type_map = self._account_type_map(parsed['company'])
            type_ids = [aid for aid, t in type_map.items()
                        if t in EXPENSE_TYPES + COGS_TYPES]
            partner_id = int(payload.get('partner_id') or 0)
            domain += [
                ('account_id', 'in', type_ids or [0]),
                ('partner_id', '=', partner_id),
                ('date', '>=', parsed['date_from']),
                ('date', '<=', parsed['date_to']),
            ]
            name = payload.get('label') or _('Compras del proveedor')
        elif drill_type == 'custom_kpi':
            # Drill-down de un KPI personalizado (V20 Fase 2 #1).
            account_ids = [int(x) for x in (payload.get('account_ids') or []) if x]
            from_beginning = bool(payload.get('from_beginning'))
            domain += [('account_id', 'in', account_ids or [0])]
            if not from_beginning and parsed['date_from']:
                domain.append(('date', '>=', parsed['date_from']))
            if parsed['date_to']:
                domain.append(('date', '<=', parsed['date_to']))
            name = payload.get('label') or _('Detalle del KPI personalizado')
        elif drill_type == 'config_kpi':
            # Drill-down para KPIs basados en cuentas configurables
            # (intereses, impuestos, depreciacion, inventario).
            maps = self._config_account_maps(parsed['company'])
            kpi_key = payload.get('kpi_key')
            mapping = {
                'interest_expense': 'interest',
                'tax_expense': 'tax',
                'depreciation': 'depreciation',
                'inventory_turnover': 'inventory',
            }
            map_key = mapping.get(kpi_key)
            ids = list(maps.get(map_key) or []) if map_key else []
            domain += [
                ('account_id', 'in', ids or [0]),
                ('date', '>=', parsed['date_from']),
                ('date', '<=', parsed['date_to']),
            ]
            name = payload.get('label') or _('Detalle del indicador')
        else:
            domain += [('date', '>=', parsed['date_from']), ('date', '<=', parsed['date_to'])]
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {'create': False},
            'target': 'current',
        }

    # ------------------------------------------------------------------
    # Helpers para drill-down
    # ------------------------------------------------------------------
    def _account_ids_for_types(self, parsed, account_types):
        """Devuelve los account_id de la compañía cuyos tipos están en ``account_types``."""
        if not account_types:
            return []
        type_map = self._account_type_map(parsed['company'])
        types = set(account_types)
        return [aid for aid, t in type_map.items() if t in types]

    def _month_bounds(self, month_key, parsed):
        """Convierte ``YYYY-MM`` a (date_from, date_to) recortados al período."""
        from datetime import date
        try:
            year, month = month_key.split('-')
            year, month = int(year), int(month)
            first = date(year, month, 1)
            last = (first + relativedelta(months=1)) - timedelta(days=1)
        except Exception:
            first, last = parsed['date_from'], parsed['date_to']
        first = max(first, parsed['date_from'])
        last = min(last, parsed['date_to'])
        return first, last

    def _aging_bucket_bounds(self, bucket, period_length=30):
        """Devuelve (from_days, to_days) del tramo (índice 0..5).

        - 0: por vencer
        - 1..4: tramos de ``period_length`` días
        - 5: más allá del cuarto tramo
        """
        pl = int(period_length or 30)
        bucket = int(bucket)
        if bucket == 0:
            return (None, None)
        if bucket == 5:
            return (pl * 4 + 1, None)
        start = pl * (bucket - 1) + 1
        end = pl * bucket
        return (start, end)

    def _filter_lines_by_aging(self, domain, on_date, from_days, to_days):
        """Filtra apuntes en Python por días vencidos respecto a ``on_date``."""
        AML = self.env['account.move.line']
        rows = AML.search_read(domain, ['id', 'date', 'date_maturity'])
        out = []
        for r in rows:
            d = r.get('date_maturity') or r.get('date')
            if not d:
                continue
            days = (on_date - d).days
            if from_days is None and to_days is None:
                if days < 1:
                    out.append(r['id'])
            elif to_days is None:
                if days >= from_days:
                    out.append(r['id'])
            else:
                if from_days <= days <= to_days:
                    out.append(r['id'])
        return out

    # ------------------------------------------------------------------
    # V20 Fase 2 — Constructor de KPIs personalizados (#1)
    # ------------------------------------------------------------------
    @api.model
    def get_custom_kpis(self, filters):
        """Evalúa los KPIs personalizados visibles para el usuario actual.

        Respeta los filtros del tablero (compañía, fechas, diarios, sucursal,
        analítica). Devuelve también la comparación si está activada.
        """
        parsed = self._parse_filters(filters)
        company = parsed['company']
        Kpi = self.env['gn.financial.dashboard.kpi']
        kpis = Kpi.search([
            ('company_id', '=', company.id),
            ('active', '=', True),
        ])
        compare, _prev = None, None
        if parsed.get('comparison') != 'none':
            compare, _prev = self._build_compare(
                parsed, self._account_type_map(company)
            )
        cmp_dates = self._comparison_dates(
            parsed['date_from'], parsed['date_to'], parsed['comparison']
        )

        # Cache de strict/asof por compañía para evitar consultas duplicadas
        # cuando varios KPIs usan los mismos sumarios.
        cache = {'strict': None, 'asof': None, 'prev_strict': None,
                 'prev_asof': None}
        items = []
        for k in kpis:
            try:
                cur = self._evaluate_custom_kpi(k, filters, cache=cache,
                                                 parsed=parsed)
                prev_val = None
                if cmp_dates:
                    prev_val = self._evaluate_custom_kpi(
                        k, filters, cache=cache, parsed=parsed,
                        cmp_dates=cmp_dates,
                    )['value']
                items.append({
                    'id': k.id,
                    'code': k.code,
                    'name': k.name,
                    'description': k.description or '',
                    'category': k.category,
                    'icon': k.icon or 'fa-bullseye',
                    'format_mode': k.format_mode,
                    'decimal_places': k.decimal_places,
                    'trend_mode': k.trend_mode,
                    'target_value': k.target_value,
                    'warning_threshold': k.warning_threshold,
                    'show_in_overview': k.show_in_overview,
                    'show_in_my_kpis': k.show_in_my_kpis,
                    'value': cur['value'],
                    'formatted': self._format_kpi_value(
                        cur['value'], k.format_mode, k.decimal_places,
                        company.currency_id,
                    ),
                    'prev_value': prev_val,
                    'account_ids': cur.get('account_ids') or [],
                })
            except Exception as e:
                # No tumbar el dashboard por un KPI mal definido.
                items.append({
                    'id': k.id, 'code': k.code, 'name': k.name,
                    'error': str(e), 'value': 0.0, 'formatted': '—',
                })
        return {
            'items': items,
            'currency': self._currency_payload(company.currency_id),
            'can_configure': self.env.user.has_group('account.group_account_manager'),
        }

    def _evaluate_custom_kpi(self, kpi, filters, cache=None, parsed=None,
                             cmp_dates=None):
        """Calcula un KPI personalizado y devuelve ``{value, account_ids}``.

        ``cache`` permite compartir los sumarios contables entre múltiples
        KPIs en la misma llamada. ``cmp_dates`` permite evaluar el KPI en el
        período comparativo (re-llamada con otras fechas).
        """
        if parsed is None:
            parsed = self._parse_filters(filters)
        company = parsed['company']
        type_map = self._account_type_map(company)
        if cmp_dates:
            df, dt = cmp_dates
        else:
            df, dt = parsed['date_from'], parsed['date_to']

        if cache is None or cmp_dates:
            local_cache = {'strict': None, 'asof': None}
        else:
            local_cache = cache

        # Sumarios contables (con cache para no recalcular).
        def _strict():
            key = 'prev_strict' if cmp_dates else 'strict'
            if local_cache.get(key) is None:
                local_cache[key] = self._per_account_sums(parsed, df, dt)
            return local_cache[key]

        def _asof():
            key = 'prev_asof' if cmp_dates else 'asof'
            if local_cache.get(key) is None:
                local_cache[key] = self._per_account_sums(
                    parsed, df, dt, from_beginning=True,
                )
            return local_cache[key]

        def _component(kind, account_ids, type_keys, sign_mode, period_mode):
            per = _asof() if period_mode == 'asof' else _strict()
            ids = []
            if kind == 'account_balance':
                ids = list(account_ids or [])
            elif kind == 'account_type_sum':
                keys = set(k.strip() for k in (type_keys or '').split(',') if k.strip())
                ids = [aid for aid, t in type_map.items() if t in keys]
            return self._sum_by_sign(per, ids, sign_mode), ids

        if kpi.formula_type == 'account_balance':
            val, ids = _component(
                'account_balance', kpi.account_ids.ids, '',
                kpi.sign_mode, kpi.period_mode,
            )
            return {'value': val, 'account_ids': ids}
        if kpi.formula_type == 'account_type_sum':
            val, ids = _component(
                'account_type_sum', None, kpi.account_type_keys,
                kpi.sign_mode, kpi.period_mode,
            )
            return {'value': val, 'account_ids': ids}
        if kpi.formula_type == 'ratio':
            num, num_ids = _component(
                kpi.numerator_kind, kpi.numerator_account_ids.ids,
                kpi.numerator_type_keys, kpi.numerator_sign, kpi.period_mode,
            )
            den, _den_ids = _component(
                kpi.denominator_kind, kpi.denominator_account_ids.ids,
                kpi.denominator_type_keys, kpi.denominator_sign, kpi.period_mode,
            )
            value = (num / den) if den else 0.0
            if kpi.percent_multiplier:
                value *= 100.0
            return {'value': value, 'account_ids': num_ids}
        if kpi.formula_type == 'expression':
            # Variables disponibles: KPIs nativos del período + códigos de
            # otros KPIs personalizados (recursión simple, 1 nivel).
            native = self._kpis_for_period(parsed, type_map, df, dt)
            env_vals = {k: v for k, v in native.items() if not k.startswith('_')}
            # Carga otros KPIs custom del mismo company para resolver refs.
            others = self.env['gn.financial.dashboard.kpi'].search([
                ('company_id', '=', company.id),
                ('active', '=', True),
                ('id', '!=', kpi.id),
                ('formula_type', '!=', 'expression'),
            ])
            for o in others:
                try:
                    env_vals[o.code] = self._evaluate_custom_kpi(
                        o, filters, cache=local_cache, parsed=parsed,
                        cmp_dates=cmp_dates,
                    )['value']
                except Exception:
                    env_vals[o.code] = 0.0
            value = self.env['gn.financial.dashboard.kpi']._safe_eval(
                kpi.expression, env_vals,
            )
            return {'value': value, 'account_ids': []}
        return {'value': 0.0, 'account_ids': []}

    def _sum_by_sign(self, per_account, account_ids, sign_mode):
        """Suma de los apuntes por modo de signo."""
        if not account_ids:
            return 0.0
        ids = set(account_ids)
        total = 0.0
        for aid in ids:
            v = per_account.get(aid)
            if not v:
                continue
            if sign_mode == 'debit':
                total += v.get('debit', 0.0)
            elif sign_mode == 'credit':
                total += v.get('credit', 0.0)
            elif sign_mode == 'invert':
                total -= v.get('balance', 0.0)
            else:
                total += v.get('balance', 0.0)
        return total

    def _format_kpi_value(self, value, fmt, decimals, currency):
        """Formateo consistente para tarjetas y tooltips de KPIs personalizados."""
        value = float(value or 0.0)
        d = max(0, int(decimals or 0))
        if fmt == 'percent':
            return ('%.{d}f%%'.format(d=d)) % value
        if fmt == 'days':
            return ('%.{d}f d'.format(d=d)) % value
        if fmt == 'ratio':
            return ('%.{d}f'.format(d=d)) % value
        if fmt == 'number':
            return ('%.{d}f'.format(d=d)) % value
        symbol = (currency.symbol or '') if currency else ''
        return '%s%s' % (symbol, ('{:,.%df}' % d).format(value))

    # ------------------------------------------------------------------
    # V20 Fase 2 — Espacios de trabajo (#2 + #20)
    # ------------------------------------------------------------------
    @api.model
    def get_workspaces(self, company_id=None):
        """Lista los workspaces del usuario + los compartidos en su compañía."""
        company = self.env['res.company'].browse(
            company_id or self.env.company.id
        )
        company.check_access('read')
        WS = self.env['gn.financial.dashboard.workspace']
        own = WS.search([
            ('user_id', '=', self.env.user.id),
            ('company_id', '=', company.id),
        ])
        shared = WS.search([
            ('shared', '=', True),
            ('company_id', '=', company.id),
            ('user_id', '!=', self.env.user.id),
        ])
        if not own:
            WS.get_or_create_default_for(self.env.user, company)
            own = WS.search([
                ('user_id', '=', self.env.user.id),
                ('company_id', '=', company.id),
            ])
        active = own.filtered(lambda w: w.is_default) or own[:1]
        return {
            'workspaces': [w.to_payload() for w in (own | shared)],
            'active_id': active.id if active else False,
        }

    @api.model
    def save_workspace(self, payload):
        """Crea/actualiza un workspace del usuario actual.

        ``payload`` admite: ``id`` (opcional), ``name``, ``layout`` (dict),
        ``shared`` (bool), ``is_default`` (bool), ``company_id``.
        """
        company = self.env['res.company'].browse(
            payload.get('company_id') or self.env.company.id
        )
        company.check_access('read')
        WS = self.env['gn.financial.dashboard.workspace']
        ws_id = payload.get('id')
        vals = {
            'name': payload.get('name') or _('Mi tablero'),
            'shared': bool(payload.get('shared')),
            'is_default': bool(payload.get('is_default')),
            'company_id': company.id,
            'user_id': self.env.user.id,
        }
        layout = payload.get('layout') or {}
        if not isinstance(layout, dict):
            raise UserError(_('El layout debe ser un objeto JSON.'))
        if ws_id:
            ws = WS.browse(int(ws_id))
            # Solo el propietario puede modificar (los compartidos son de solo lectura).
            if ws.user_id != self.env.user:
                raise UserError(_(
                    'No puedes modificar un workspace de otro usuario. '
                    'Duplícalo para personalizarlo.'))
            ws.write(vals)
            ws.set_layout(layout)
            return ws.to_payload()
        ws = WS.create(vals)
        ws.set_layout(layout)
        return ws.to_payload()

    @api.model
    def delete_workspace(self, workspace_id):
        WS = self.env['gn.financial.dashboard.workspace']
        ws = WS.browse(int(workspace_id))
        if not ws.exists():
            raise UserError(_('Workspace inexistente.'))
        if ws.user_id != self.env.user:
            raise UserError(_('Solo el propietario puede eliminarlo.'))
        ws.unlink()
        return True

    @api.model
    def duplicate_workspace(self, workspace_id, new_name=None):
        WS = self.env['gn.financial.dashboard.workspace']
        ws = WS.browse(int(workspace_id))
        if not ws.exists():
            raise UserError(_('Workspace inexistente.'))
        copy = ws.copy({
            'user_id': self.env.user.id,
            'name': new_name or _('%s (copia)') % ws.name,
            'is_default': False,
            'shared': False,
        })
        return copy.to_payload()

    # ------------------------------------------------------------------
    # V20 Fase 2 — Objetivos estratégicos (#19)
    # ------------------------------------------------------------------
    @api.model
    def get_goals_progress(self, filters):
        """Evalúa los objetivos vs. los KPIs actuales (nativos o custom)."""
        parsed = self._parse_filters(filters)
        company = parsed['company']
        Goal = self.env['gn.financial.dashboard.goal']
        goals = Goal.search([
            ('company_id', '=', company.id),
            ('active', '=', True),
        ])
        if not goals:
            return {'goals': [], 'summary': {'attained': 0, 'in_progress': 0,
                                              'overdue': 0, 'total': 0}}
        # Pre-calculo de KPIs nativos.
        type_map = self._account_type_map(company)
        native_kpis = self._kpis_for_period(parsed, type_map,
                                            parsed['date_from'], parsed['date_to'])
        # Cache de KPIs custom para no recomputar varios veces.
        custom_cache = {}
        results = []
        counts = {'attained': 0, 'in_progress': 0, 'overdue': 0}
        for g in goals:
            if g.kpi_source == 'native':
                current = float(native_kpis.get(g.kpi_key) or 0.0)
            else:
                cid = g.custom_kpi_id.id
                if cid not in custom_cache:
                    custom_cache[cid] = self._evaluate_custom_kpi(
                        g.custom_kpi_id, filters, parsed=parsed,
                    )['value']
                current = float(custom_cache[cid] or 0.0)
            status = g.evaluate_status(current)
            counts[status['status']] = counts.get(status['status'], 0) + 1
            payload = g.to_payload()
            payload.update(status)
            # Formato del valor según el formato del KPI custom o moneda nativa.
            if g.kpi_source == 'custom':
                payload['formatted_current'] = self._format_kpi_value(
                    status['current_value'], g.custom_kpi_id.format_mode,
                    g.custom_kpi_id.decimal_places, company.currency_id,
                )
                payload['formatted_target'] = self._format_kpi_value(
                    g.target_value, g.custom_kpi_id.format_mode,
                    g.custom_kpi_id.decimal_places, company.currency_id,
                )
            else:
                # Heurística: KPIs con "margin"/"ratio"/"rate" → %; otros → money.
                key = g.kpi_key or ''
                fmt = 'percent' if any(x in key for x in
                                       ('margin', 'rate', 'ratio')) else 'money'
                payload['formatted_current'] = self._format_kpi_value(
                    status['current_value'], fmt, 2, company.currency_id,
                )
                payload['formatted_target'] = self._format_kpi_value(
                    g.target_value, fmt, 2, company.currency_id,
                )
            results.append(payload)
        results.sort(key=lambda r: (r['status'] != 'overdue',
                                     r['status'] != 'in_progress',
                                     -r.get('weight', 0)))
        return {
            'goals': results,
            'summary': {
                'attained': counts.get('attained', 0),
                'in_progress': counts.get('in_progress', 0),
                'overdue': counts.get('overdue', 0),
                'total': len(goals),
            },
            'currency': self._currency_payload(company.currency_id),
        }

    # ------------------------------------------------------------------
    # Exportaciones (solo gestor contable)
    # ------------------------------------------------------------------
    def _check_export_access(self):
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_('Necesita permisos de gestor contable para exportar.'))

    @api.model
    def action_export_pdf(self, filters):
        self._check_export_access()
        return self.env.ref(
            'gn_financial_dashboard.action_report_financial_executive'
        ).report_action([], data={'filters': filters})

    @api.model
    def action_export_excel(self, filters):
        self._check_export_access()
        if xlsxwriter is None:
            raise UserError(_('La librería xlsxwriter no está instalada en el servidor.'))
        parsed = self._parse_filters(filters)
        payload = self.get_dashboard_data(filters)
        content = self._build_excel(parsed, payload, filters)
        fname = 'tablero_financiero_%s_%s.xlsx' % (
            fields.Date.to_string(parsed['date_from']),
            fields.Date.to_string(parsed['date_to']),
        )
        attachment = self.env['ir.attachment'].create({
            'name': fname,
            'type': 'binary',
            'datas': base64.b64encode(content),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

    def _build_excel(self, parsed, payload, filters):
        buffer = io.BytesIO()
        wb = xlsxwriter.Workbook(buffer, {'in_memory': True})
        currency = payload.get('currency', {}).get('symbol', '')
        money_fmt = wb.add_format({'num_format': '#,##0.00'})
        title_fmt = wb.add_format({'bold': True, 'font_size': 14})
        head_fmt = wb.add_format({'bold': True, 'bg_color': '#1f2d3d', 'font_color': 'white', 'border': 1})
        label_fmt = wb.add_format({'bold': True})

        def sheet_table(ws, headers, rows, start_row=0):
            for c, h in enumerate(headers):
                ws.write(start_row, c, h, head_fmt)
            r = start_row + 1
            for row in rows:
                for c, val in enumerate(row):
                    fmt = money_fmt if isinstance(val, (int, float)) else None
                    ws.write(r, c, val, fmt)
                r += 1
            return r

        # Resumen
        ws = wb.add_worksheet(_('Resumen'))
        ws.set_column(0, 0, 30)
        ws.set_column(1, 1, 20)
        ws.write(0, 0, _('Tablero financiero (%s)') % currency, title_fmt)
        ws.write(1, 0, _('Período'), label_fmt)
        ws.write(1, 1, '%s — %s' % (payload['period']['date_from'], payload['period']['date_to']))
        ws.write(2, 0, _('Salud financiera'), label_fmt)
        ws.write(2, 1, '%s / 100 (%s)' % (payload['health']['score'], payload['health']['label']))
        kpis = payload['kpis']
        kpi_rows = [
            (_('Ingresos'), kpis['revenue']),
            (_('Costo de ventas'), kpis['cogs']),
            (_('Utilidad bruta'), kpis['gross_profit']),
            (_('Gastos'), kpis['expenses']),
            (_('Utilidad neta'), kpis['net_profit']),
            (_('Margen neto %'), kpis['net_margin']),
            (_('Por cobrar'), kpis['receivables']),
            (_('Por pagar'), kpis['payables']),
            (_('Saldo bancario'), kpis['closing_bank']),
            (_('Capital de trabajo'), kpis['working_capital']),
        ]
        sheet_table(ws, [_('Indicador'), _('Valor')], kpi_rows, start_row=4)

        # Rentabilidad
        ws = wb.add_worksheet(_('Rentabilidad'))
        ws.set_column(0, 0, 22)
        sheet_table(ws, [_('Indicador'), _('Valor')], [
            (_('Ingresos'), kpis['revenue']),
            (_('Costo de ventas'), kpis['cogs']),
            (_('Utilidad bruta'), kpis['gross_profit']),
            (_('Margen bruto %'), kpis['gross_margin']),
            (_('Gastos'), kpis['expenses']),
            (_('Utilidad neta'), kpis['net_profit']),
            (_('Margen neto %'), kpis['net_margin']),
        ])

        # Liquidez
        ws = wb.add_worksheet(_('Liquidez'))
        ws.set_column(0, 0, 22)
        sheet_table(ws, [_('Indicador'), _('Valor')], [
            (_('Saldo bancario'), kpis['closing_bank']),
            (_('Flujo de caja'), kpis['cash_surplus']),
            (_('Por cobrar'), kpis['receivables']),
            (_('Por pagar'), kpis['payables']),
            (_('Capital de trabajo'), kpis['working_capital']),
            (_('Razón corriente'), kpis.get('current_ratio', 0.0)),
        ])

        # Cuentas por cobrar (ranking)
        ws = wb.add_worksheet(_('Por cobrar'))
        ws.set_column(0, 0, 35)
        rows = [
            (it['name'], it['pending'], it['overdue'], it['avg_days'], it['pct'])
            for it in payload.get('partner_rankings', {}).get('receivable', {}).get('items', [])
        ]
        sheet_table(ws, [_('Cliente'), _('Pendiente'), _('Vencido'), _('Días prom.'), _('% cartera')], rows)

        # Cuentas por pagar (ranking)
        ws = wb.add_worksheet(_('Por pagar'))
        ws.set_column(0, 0, 35)
        rows = [
            (it['name'], it['pending'], it['overdue'], it['avg_days'], it['pct'])
            for it in payload.get('partner_rankings', {}).get('payable', {}).get('items', [])
        ]
        sheet_table(ws, [_('Proveedor'), _('Pendiente'), _('Vencido'), _('Días prom.'), _('% cartera')], rows)

        # Gastos (ranking)
        ws = wb.add_worksheet(_('Gastos'))
        ws.set_column(0, 0, 35)
        rows = [
            (it['name'], it['amount'], it['pct'])
            for it in payload.get('expense_ranking', {}).get('items', [])
        ]
        sheet_table(ws, [_('Cuenta'), _('Monto'), _('% del total')], rows)

        # Detalle contable (cuentas con saldo del período)
        ws = wb.add_worksheet(_('Detalle'))
        ws.set_column(0, 1, 18)
        ws.set_column(2, 2, 35)
        detail = self.get_account_detail(filters, 'net_assets')
        rows = [
            (r['code'], r['account_type'], r['name'], r['balance'])
            for r in detail.get('rows', [])
        ]
        sheet_table(ws, [_('Código'), _('Tipo'), _('Cuenta'), _('Saldo')], rows)

        wb.close()
        buffer.seek(0)
        return buffer.read()

    @api.model
    def open_bi_report(self, report_type):
        xmlid = BI_REPORT_ACTIONS.get(report_type)
        if not xmlid:
            raise UserError(_('Reporte no disponible.'))
        action = self.env.ref(xmlid, raise_if_not_found=False)
        if not action:
            raise UserError(_(
                'El módulo de Reportes Financieros (BI) no está instalado.'
            ))
        return action.read()[0]
