# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

"""Estado de Flujo de Efectivo (Direct Method).

Replica la lógica del módulo Enterprise ``account_reports`` (ver
``account_cash_flow_report.py``) adaptándola al patrón del resto de
informes del módulo ``bi_financial_reports_comm`` (un método
``get_data_cash_flow`` que recibe los filtros vía ``self.env.context`` y
devuelve un diccionario con las secciones listas para renderizar).

El reporte sigue el método directo:
- Cuentas de liquidez = cuentas usadas por diarios bank/cash + cuentas
  de métodos de pago.
- Para cada asiento que toca una cuenta de liquidez en el período se
  miran sus contracuentas (no liquidez):
    * Si la contracuenta NO está conciliada con un asiento fuera del
      grupo de liquidez, se aporta su saldo completo (negado).
    * Si la contracuenta SÍ está conciliada con un asiento externo
      (típicamente una factura), la parte conciliada cancela la línea
      del movimiento de liquidez y se aporta, en su lugar, el saldo
      proporcional de las líneas del asiento conciliado (factura) según
      el porcentaje pagado.
- Cada aporte se clasifica según el tipo de cuenta (receivable/payable)
  o el tag de cuenta (operating / investing / financing).
"""

import base64
import io

import xlsxwriter
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.tools.date_utils import get_fiscal_year, get_month, get_quarter


class CashFlowReport(models.Model):
    _name = 'cash.flow.report'
    _description = 'Cash Flow Report'

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------
    @api.model
    def _get_layout(self):
        """Estructura del reporte (claves estables consumidas en JS)."""
        return [
            (
                'operating_activities',
                _('Flujos de efectivo de actividades de operación'),
                [
                    ('advance_payments_customer', _('Anticipos recibidos de clientes')),
                    ('received_operating_activities', _('Efectivo recibido por actividades de operación')),
                    ('advance_payments_suppliers', _('Anticipos pagados a proveedores')),
                    ('paid_operating_activities', _('Efectivo pagado por actividades de operación')),
                ],
            ),
            (
                'investing_activities',
                _('Flujos de efectivo de actividades de inversión y extraordinarias'),
                [
                    ('investing_activities_cash_in', _('Entradas de efectivo')),
                    ('investing_activities_cash_out', _('Salidas de efectivo')),
                ],
            ),
            (
                'financing_activities',
                _('Flujos de efectivo de actividades de financiamiento'),
                [
                    ('financing_activities_cash_in', _('Entradas de efectivo')),
                    ('financing_activities_cash_out', _('Salidas de efectivo')),
                ],
            ),
            (
                'unclassified_activities',
                _('Flujos de efectivo de actividades no clasificadas'),
                [
                    ('unclassified_activities_cash_in', _('Entradas de efectivo')),
                    ('unclassified_activities_cash_out', _('Salidas de efectivo')),
                ],
            ),
        ]

    @api.model
    def _build_empty_sections(self):
        sections = {}
        for sec_key, sec_name, subs in self._get_layout():
            sections[sec_key] = {
                'name': sec_name,
                'total': 0.0,
                'subsections': {
                    sub_key: {
                        'name': sub_name,
                        'total': 0.0,
                        'accounts': {},
                    }
                    for sub_key, sub_name in subs
                },
            }
        return sections

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------
    @api.model
    def _get_cashflow_tag_map(self):
        """Devuelve {tag_id: 'operating' | 'investing' | 'financing'}."""
        result = {}
        mapping = {
            'account.account_tag_operating': 'operating',
            'account.account_tag_investing': 'investing',
            'account.account_tag_financing': 'financing',
        }
        for xmlid, key in mapping.items():
            tag = self.env.ref(xmlid, raise_if_not_found=False)
            if tag:
                result[tag.id] = key
        return result

    # ------------------------------------------------------------------
    # Cuentas de liquidez
    # ------------------------------------------------------------------
    @api.model
    def _get_payment_account_ids(self, journal_ids):
        """Devuelve la tupla de IDs de cuentas consideradas liquidez.

        Replica la consulta del Enterprise: cuentas por defecto de
        diarios bank/cash que sean asset_cash o liability_credit_card,
        más las cuentas configuradas en los métodos de pago de esos
        diarios.
        """
        Journal = self.env['account.journal']
        if journal_ids:
            journals = Journal.browse(journal_ids).exists()
        else:
            journals = Journal.search([('type', 'in', ('bank', 'cash', 'general'))])

        account_ids = set()
        for journal in journals:
            default_acc = journal.default_account_id
            if default_acc and default_acc.account_type in (
                'asset_cash', 'liability_credit_card',
            ):
                account_ids.add(default_acc.id)
            for pml in (
                journal.inbound_payment_method_line_ids
                | journal.outbound_payment_method_line_ids
            ):
                if pml.payment_account_id:
                    account_ids.add(pml.payment_account_id.id)

        return tuple(account_ids)

    # ------------------------------------------------------------------
    # Saldos de liquidez (apertura / cierre)
    # ------------------------------------------------------------------
    @api.model
    def _liquidity_balance(self, payment_account_ids, journal_ids, target_move,
                          date_to, include_date_to=True):
        """Suma el balance de las cuentas de liquidez hasta ``date_to``.

        :param include_date_to: si False, suma estrictamente antes de
            ``date_to`` (útil para el saldo de apertura).
        """
        if not payment_account_ids:
            return {}, 0.0
        params = [tuple(payment_account_ids)]
        where = ['aml.account_id IN %s']
        if target_move == 'posted':
            where.append("aml.parent_state = 'posted'")
        if journal_ids:
            where.append('aml.journal_id IN %s')
            params.append(tuple(journal_ids))
        if include_date_to:
            where.append('aml.date <= %s')
        else:
            where.append('aml.date < %s')
        params.append(date_to)

        query = """
            SELECT aml.account_id, SUM(aml.balance) AS balance
            FROM account_move_line aml
            WHERE %s
            GROUP BY aml.account_id
        """ % ' AND '.join(where)
        self.env.cr.execute(query, params)
        rows = self.env.cr.dictfetchall()

        accounts_meta = self._get_accounts_meta([r['account_id'] for r in rows])
        accounts = {}
        total = 0.0
        for row in rows:
            balance = row['balance'] or 0.0
            meta = accounts_meta.get(row['account_id'], {})
            accounts[row['account_id']] = {
                'id': row['account_id'],
                'code': meta.get('code'),
                'name': meta.get('name'),
                'balance': balance,
            }
            total += balance
        return accounts, total

    @api.model
    def _get_accounts_meta(self, account_ids):
        """Devuelve {id: {'code', 'name', 'account_type'}} usando ORM
        para que el campo ``code`` (JSON multicompañía) se resuelva
        correctamente en Odoo 19.
        """
        if not account_ids:
            return {}
        records = self.env['account.account'].browse(set(account_ids)).exists()
        return {
            acc.id: {
                'code': acc.code,
                'name': acc.name,
                'account_type': acc.account_type,
            }
            for acc in records
        }

    # ------------------------------------------------------------------
    # Movimientos de liquidez (contracuentas)
    # ------------------------------------------------------------------
    @api.model
    def _get_liquidity_moves_data(self, payment_account_ids, journal_ids,
                                  target_move, date_from, date_to,
                                  cashflow_tag_ids):
        """Para cada contracuenta de un movimiento de liquidez, devuelve
        el aporte al cash flow ya negado (cash effect).

        Estructura del retorno:
            list[ dict(account_id, account_code, account_name,
                       account_type, account_tag_id, balance) ]
        """
        if not payment_account_ids:
            return []

        # 1) IDs de movimientos que tocan alguna cuenta de liquidez en el período.
        params = [tuple(payment_account_ids), date_from, date_to]
        where = [
            'aml.account_id IN %s',
            'aml.date BETWEEN %s AND %s',
        ]
        if target_move == 'posted':
            where.append("aml.parent_state = 'posted'")
        if journal_ids:
            where.append('aml.journal_id IN %s')
            params.append(tuple(journal_ids))

        self.env.cr.execute(
            "SELECT DISTINCT aml.move_id FROM account_move_line aml WHERE "
            + ' AND '.join(where),
            params,
        )
        move_ids = tuple(r[0] for r in self.env.cr.fetchall())
        if not move_ids:
            return []

        # 2) Tres consultas UNION: porción conciliada por crédito, por
        #    débito y balance total. La suma final, una vez negada, da
        #    el aporte real al flujo de caja.
        tag_filter = (
            "LEFT JOIN account_account_account_tag aat "
            "ON aat.account_account_id = aml.account_id "
            "AND aat.account_account_tag_id IN %s"
        )
        params_credit = [move_ids, payment_account_ids, date_from, date_to]
        params_debit = [move_ids, payment_account_ids, date_from, date_to]
        params_total = [move_ids, payment_account_ids]

        if cashflow_tag_ids:
            tag_tuple = tuple(cashflow_tag_ids)
            params_credit.insert(0, tag_tuple)
            params_debit.insert(0, tag_tuple)
            params_total.insert(0, tag_tuple)
            tag_join = tag_filter
            tag_select = 'aat.account_account_tag_id'
        else:
            tag_join = ''
            tag_select = 'NULL'

        query_credit = """
            SELECT aml.account_id,
                   {tag_select} AS account_tag_id,
                   COALESCE(SUM(apr.amount), 0.0) AS balance
            FROM account_move_line aml
            {tag_join}
            LEFT JOIN account_partial_reconcile apr
                ON apr.credit_move_id = aml.id
            WHERE aml.move_id IN %s
              AND aml.account_id NOT IN %s
              AND apr.max_date BETWEEN %s AND %s
            GROUP BY aml.account_id, {tag_select}
        """.format(tag_join=tag_join, tag_select=tag_select)

        query_debit = """
            SELECT aml.account_id,
                   {tag_select} AS account_tag_id,
                   COALESCE(-SUM(apr.amount), 0.0) AS balance
            FROM account_move_line aml
            {tag_join}
            LEFT JOIN account_partial_reconcile apr
                ON apr.debit_move_id = aml.id
            WHERE aml.move_id IN %s
              AND aml.account_id NOT IN %s
              AND apr.max_date BETWEEN %s AND %s
            GROUP BY aml.account_id, {tag_select}
        """.format(tag_join=tag_join, tag_select=tag_select)

        query_total = """
            SELECT aml.account_id,
                   {tag_select} AS account_tag_id,
                   COALESCE(SUM(aml.balance), 0.0) AS balance
            FROM account_move_line aml
            {tag_join}
            WHERE aml.move_id IN %s
              AND aml.account_id NOT IN %s
            GROUP BY aml.account_id, {tag_select}
        """.format(tag_join=tag_join, tag_select=tag_select)

        full_query = ' UNION ALL '.join([query_credit, query_debit, query_total])
        self.env.cr.execute(
            full_query,
            params_credit + params_debit + params_total,
        )
        rows = self.env.cr.dictfetchall()

        accounts_meta = self._get_accounts_meta([r['account_id'] for r in rows])

        # 3) Agrupa por (cuenta, tag) y NIEGA el saldo (perspectiva de caja).
        grouped = {}
        for row in rows:
            aid = row['account_id']
            meta = accounts_meta.get(aid, {})
            key = (aid, row['account_tag_id'])
            grouped.setdefault(key, {
                'account_id': aid,
                'account_code': meta.get('code'),
                'account_name': meta.get('name'),
                'account_type': meta.get('account_type'),
                'account_tag_id': row['account_tag_id'],
                'balance': 0.0,
            })
            grouped[key]['balance'] -= row['balance']
        return list(grouped.values())

    # ------------------------------------------------------------------
    # Movimientos conciliados (facturas) - se valoran al porcentaje pagado
    # ------------------------------------------------------------------
    @api.model
    def _get_reconciled_moves_data(self, payment_account_ids, journal_ids,
                                   target_move, date_from, date_to,
                                   cashflow_tag_ids):
        """Para los asientos reconciliados con movimientos de liquidez
        (típicamente facturas), aporta sus líneas al porcentaje pagado.
        """
        if not payment_account_ids:
            return []

        # Reusar el mismo conjunto de move_ids de liquidez.
        params = [tuple(payment_account_ids), date_from, date_to]
        where = [
            'aml.account_id IN %s',
            'aml.date BETWEEN %s AND %s',
        ]
        if target_move == 'posted':
            where.append("aml.parent_state = 'posted'")
        if journal_ids:
            where.append('aml.journal_id IN %s')
            params.append(tuple(journal_ids))

        self.env.cr.execute(
            "SELECT DISTINCT aml.move_id FROM account_move_line aml WHERE "
            + ' AND '.join(where),
            params,
        )
        liquidity_move_ids = tuple(r[0] for r in self.env.cr.fetchall())
        if not liquidity_move_ids:
            return []

        # 1) Por cada (asiento conciliado, cuenta) calcular el monto
        #    reconciliado dentro del período (sumando contribuciones por
        #    crédito y débito en partial_reconciles del período).
        self.env.cr.execute(
            """
            (SELECT
                debit_line.move_id AS move_id,
                debit_line.account_id AS account_id,
                SUM(apr.amount) AS amount
             FROM account_move_line credit_line
             JOIN account_partial_reconcile apr
                 ON apr.credit_move_id = credit_line.id
             JOIN account_move_line debit_line
                 ON debit_line.id = apr.debit_move_id
             WHERE credit_line.move_id IN %s
               AND credit_line.account_id NOT IN %s
               AND credit_line.credit > 0.0
               AND debit_line.move_id NOT IN %s
               AND apr.max_date BETWEEN %s AND %s
             GROUP BY debit_line.move_id, debit_line.account_id)
            UNION ALL
            (SELECT
                credit_line.move_id AS move_id,
                credit_line.account_id AS account_id,
                -SUM(apr.amount) AS amount
             FROM account_move_line debit_line
             JOIN account_partial_reconcile apr
                 ON apr.debit_move_id = debit_line.id
             JOIN account_move_line credit_line
                 ON credit_line.id = apr.credit_move_id
             WHERE debit_line.move_id IN %s
               AND debit_line.account_id NOT IN %s
               AND debit_line.debit > 0.0
               AND credit_line.move_id NOT IN %s
               AND apr.max_date BETWEEN %s AND %s
             GROUP BY credit_line.move_id, credit_line.account_id)
            """,
            [
                liquidity_move_ids, payment_account_ids, liquidity_move_ids,
                date_from, date_to,
                liquidity_move_ids, payment_account_ids, liquidity_move_ids,
                date_from, date_to,
            ],
        )
        reconciled_rows = self.env.cr.dictfetchall()
        if not reconciled_rows:
            return []

        # reconciled[move_id][account_id] = [reconciled_amount, total_amount_of_account_in_move]
        reconciled = {}
        reconciled_account_ids = set()
        for row in reconciled_rows:
            mid, aid = row['move_id'], row['account_id']
            reconciled.setdefault(mid, {}).setdefault(aid, [0.0, 0.0])
            reconciled[mid][aid][0] += row['amount'] or 0.0
            reconciled_account_ids.add(aid)

        # 2) Total por (asiento conciliado, cuenta_reconciliada) - sirve
        #    para calcular el porcentaje pagado del asiento.
        if reconciled and reconciled_account_ids:
            self.env.cr.execute(
                """
                SELECT aml.move_id, aml.account_id, SUM(aml.balance) AS balance
                FROM account_move_line aml
                WHERE aml.move_id IN %s AND aml.account_id IN %s
                GROUP BY aml.move_id, aml.account_id
                """,
                [tuple(reconciled.keys()), tuple(reconciled_account_ids)],
            )
            for row in self.env.cr.dictfetchall():
                mid, aid = row['move_id'], row['account_id']
                if aid in reconciled.get(mid, {}):
                    reconciled[mid][aid][1] += row['balance'] or 0.0

        # 3) Para cada asiento reconciliado, traer todas sus líneas y
        #    valorarlas según el porcentaje pagado. Las líneas que están
        #    en una cuenta ya reconciliada (típicamente Receivable /
        #    Payable) no se incluyen como flujo (su efecto ya está dado
        #    en la pierna del movimiento de liquidez correspondiente).
        tag_join = ''
        tag_select = 'NULL'
        params_lines = [tuple(reconciled.keys())]
        if cashflow_tag_ids:
            tag_join = (
                "LEFT JOIN account_account_account_tag aat "
                "ON aat.account_account_id = aml.account_id "
                "AND aat.account_account_tag_id IN %s"
            )
            tag_select = 'aat.account_account_tag_id'
            params_lines.insert(0, tuple(cashflow_tag_ids))

        self.env.cr.execute(
            """
            SELECT aml.move_id,
                   aml.account_id,
                   {tag_select} AS account_tag_id,
                   SUM(aml.balance) AS balance
            FROM account_move_line aml
            {tag_join}
            WHERE aml.move_id IN %s
            GROUP BY aml.move_id, aml.account_id, {tag_select}
            """.format(tag_join=tag_join, tag_select=tag_select),
            params_lines,
        )
        lines = self.env.cr.dictfetchall()
        accounts_meta = self._get_accounts_meta([l['account_id'] for l in lines])

        grouped = {}
        for line in lines:
            mid = line['move_id']
            aid = line['account_id']
            balance = line['balance'] or 0.0

            move_data = reconciled.get(mid, {})
            total_reconciled = sum(v[0] for v in move_data.values())
            total_amount = sum(v[1] for v in move_data.values())

            if total_amount and aid not in move_data:
                pct = total_reconciled / total_amount
                balance *= pct
            elif not total_amount and aid in move_data:
                # Caso especial: el asiento total balancea a 0 sobre la
                # cuenta reconciliada; sólo aportamos su parte conciliada.
                balance = -move_data[aid][0]
            else:
                continue

            meta = accounts_meta.get(aid, {})
            key = (aid, line['account_tag_id'])
            grouped.setdefault(key, {
                'account_id': aid,
                'account_code': meta.get('code'),
                'account_name': meta.get('name'),
                'account_type': meta.get('account_type'),
                'account_tag_id': line['account_tag_id'],
                'balance': 0.0,
            })
            grouped[key]['balance'] -= balance

        return list(grouped.values())

    # ------------------------------------------------------------------
    # Despacho a secciones del reporte
    # ------------------------------------------------------------------
    @api.model
    def _dispatch(self, aml_data, tag_map, sections):
        """Asigna ``aml_data`` a la subsección correspondiente."""
        balance = aml_data['balance']
        if not balance or self.env.company.currency_id.is_zero(balance):
            return

        section_key, sub_key = self._classify(aml_data, tag_map)
        if not sub_key:
            return

        sub = sections[section_key]['subsections'][sub_key]
        sub['total'] += balance
        sections[section_key]['total'] += balance

        accounts = sub['accounts']
        aid = aml_data['account_id']
        if aid not in accounts:
            accounts[aid] = {
                'id': aid,
                'code': aml_data['account_code'],
                'name': aml_data['account_name'],
                'balance': 0.0,
            }
        accounts[aid]['balance'] += balance

    @api.model
    def _classify(self, aml_data, tag_map):
        atype = aml_data.get('account_type')
        balance = aml_data['balance']
        tag_id = aml_data.get('account_tag_id')
        tag_kind = tag_map.get(tag_id) if tag_id else None

        if atype == 'asset_receivable':
            return ('operating_activities', 'advance_payments_customer')
        if atype == 'liability_payable':
            return ('operating_activities', 'advance_payments_suppliers')

        is_in = balance > 0
        if tag_kind == 'operating':
            return ('operating_activities',
                    'received_operating_activities' if is_in
                    else 'paid_operating_activities')
        if tag_kind == 'investing':
            return ('investing_activities',
                    'investing_activities_cash_in' if is_in
                    else 'investing_activities_cash_out')
        if tag_kind == 'financing':
            return ('financing_activities',
                    'financing_activities_cash_in' if is_in
                    else 'financing_activities_cash_out')
        return ('unclassified_activities',
                'unclassified_activities_cash_in' if is_in
                else 'unclassified_activities_cash_out')

    @api.model
    def _get_comparison_period_dates(self, date_from, date_to, comparison_filter,
                                     number_period, date_filter_type):
        """Misma lógica que P&L / Tax report (período fecha desde–hasta)."""
        if comparison_filter in ('no_comparison', None):
            return None
        if comparison_filter != 'specific_date' and not number_period:
            return None
        date_from = fields.Date.from_string(date_from) if isinstance(date_from, str) else date_from
        date_to = fields.Date.from_string(date_to) if isinstance(date_to, str) else date_to
        if comparison_filter == 'previous_period':
            pt = date_filter_type or 'month'
            if pt == 'month':
                cmp_to = date_to - relativedelta(months=number_period)
                cmp_from, cmp_to = get_month(cmp_to)
            elif pt == 'quarter':
                cmp_to = date_to - relativedelta(months=3 * number_period)
                cmp_from, cmp_to = get_quarter(cmp_to)
            else:
                cmp_to = date_to - relativedelta(years=number_period)
                cmp_from, cmp_to = get_fiscal_year(cmp_to)
            return {
                'date_from': cmp_from.strftime('%Y-%m-%d'),
                'date_to': cmp_to.strftime('%Y-%m-%d'),
                'string': cmp_from.strftime('%d/%m/%Y') + ' - ' + cmp_to.strftime('%d/%m/%Y'),
            }
        if comparison_filter == 'same_last_year':
            cmp_from = date_from - relativedelta(years=number_period)
            cmp_to = date_to - relativedelta(years=number_period)
            return {
                'date_from': cmp_from.strftime('%Y-%m-%d'),
                'date_to': cmp_to.strftime('%Y-%m-%d'),
                'string': cmp_from.strftime('%d/%m/%Y') + ' - ' + cmp_to.strftime('%d/%m/%Y'),
            }
        if comparison_filter == 'specific_date':
            cmp_date_to = self.env.context.get('comparison_date_to')
            if cmp_date_to:
                cmp_to = fields.Date.from_string(cmp_date_to)
                pt = date_filter_type or 'month'
                if pt == 'month':
                    cmp_from, cmp_to = get_month(cmp_to)
                elif pt == 'quarter':
                    cmp_from, cmp_to = get_quarter(cmp_to)
                else:
                    cmp_from, cmp_to = get_fiscal_year(cmp_to)
                return {
                    'date_from': cmp_from.strftime('%Y-%m-%d'),
                    'date_to': cmp_to.strftime('%Y-%m-%d'),
                    'string': cmp_from.strftime('%d/%m/%Y') + ' - ' + cmp_to.strftime('%d/%m/%Y'),
                }
        return None

    @api.model
    def _compute_cash_flow_for_period(self, date_from, date_to, journal_ids, target_move):
        """Calcula un período completo (misma forma que get_data_cash_flow)."""
        currency = self.env.company.currency_id
        currency_data = {
            'id': currency.id,
            'symbol': currency.symbol,
            'position': currency.position,
            'decimal_places': currency.decimal_places,
        }
        payment_account_ids = self._get_payment_account_ids(journal_ids)
        sections = self._build_empty_sections()
        if not payment_account_ids:
            return self._finalize_result(
                date_from, date_to, currency_data, sections,
                opening_accounts={}, closing_accounts={},
                opening_total=0.0, closing_total=0.0,
                has_draft_warning=False,
            )
        tag_map = self._get_cashflow_tag_map()
        cashflow_tag_ids = list(tag_map.keys())
        opening_accounts, opening_total = self._liquidity_balance(
            payment_account_ids, journal_ids, target_move,
            date_from, include_date_to=False,
        )
        closing_accounts, closing_total = self._liquidity_balance(
            payment_account_ids, journal_ids, target_move,
            date_to, include_date_to=True,
        )
        liquidity_data = self._get_liquidity_moves_data(
            payment_account_ids, journal_ids, target_move,
            date_from, date_to, cashflow_tag_ids,
        )
        for aml_data in liquidity_data:
            self._dispatch(aml_data, tag_map, sections)
        reconciled_data = self._get_reconciled_moves_data(
            payment_account_ids, journal_ids, target_move,
            date_from, date_to, cashflow_tag_ids,
        )
        for aml_data in reconciled_data:
            self._dispatch(aml_data, tag_map, sections)
        has_draft_warning = False
        if target_move == 'posted':
            draft_domain = [
                ('parent_state', '=', 'draft'),
                ('account_id', 'in', list(payment_account_ids)),
                ('date', '<=', date_to),
            ]
            if journal_ids:
                draft_domain.append(('journal_id', 'in', journal_ids))
            has_draft_warning = bool(
                self.env['account.move.line'].search(draft_domain, limit=1)
            )
        return self._finalize_result(
            date_from, date_to, currency_data, sections,
            opening_accounts=opening_accounts,
            closing_accounts=closing_accounts,
            opening_total=opening_total,
            closing_total=closing_total,
            has_draft_warning=has_draft_warning,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @api.model
    def get_data_cash_flow(self):
        ctx = self.env.context
        date_from = ctx.get('date_from')
        date_to = ctx.get('date_to')
        journal_ids = ctx.get('journal_ids') or []
        target_move = ctx.get('target_move') or 'all'

        today = fields.Date.today()
        if not date_from:
            date_from = today.replace(day=1)
        if not date_to:
            date_to = today
        if isinstance(date_from, str):
            date_from = fields.Date.from_string(date_from)
        if isinstance(date_to, str):
            date_to = fields.Date.from_string(date_to)

        result = self._compute_cash_flow_for_period(
            date_from, date_to, journal_ids, target_move)

        comparison_filter = ctx.get('comparison_filter', 'no_comparison')
        comparison_number = ctx.get('comparison_number_period', 1) or 1
        date_filter_type = ctx.get('date_filter_type', 'month')
        cmp_period = self._get_comparison_period_dates(
            date_from, date_to, comparison_filter, comparison_number, date_filter_type)
        if cmp_period:
            cdf = fields.Date.from_string(cmp_period['date_from'])
            cdt = fields.Date.from_string(cmp_period['date_to'])
            cmp_res = self._compute_cash_flow_for_period(
                cdf, cdt, journal_ids, target_move)
            cmp_res['label'] = cmp_period['string']
            result['comparison'] = cmp_res

        report_cur = ctx.get('report_currency_id')
        if report_cur:
            self.env['bi.report.currency.helper'].apply_cash_flow(result, report_cur)
        return result

    @api.model
    def cash_flow_owl_xlsx(self, data):
        """Exporta el dict devuelto por get_data_cash_flow (vista OWL)."""
        buf = io.BytesIO()
        workbook = xlsxwriter.Workbook(buf, {'in_memory': True})
        sheet = workbook.add_worksheet(_('Flujo de efectivo'))
        bold = workbook.add_format({'bold': True})
        money_fmt = workbook.add_format({'num_format': '#,##0.00'})
        row = 0
        sheet.write(row, 0, data.get('company') or '', bold)
        row += 1
        sheet.write(row, 0, _('Desde'), bold)
        sheet.write(row, 1, data.get('date_from') or '')
        sheet.write(row, 2, _('Hasta'), bold)
        sheet.write(row, 3, data.get('date_to') or '')
        row += 2
        sheet.write(row, 0, _('Concepto'), bold)
        sheet.write(row, 1, _('Importe'), bold)
        row += 1

        def write_row(label, amount):
            nonlocal row
            sheet.write(row, 0, label)
            sheet.write_number(row, 1, float(amount or 0), money_fmt)
            row += 1

        write_row(_('Efectivo y equivalentes, saldo inicial'), data.get('opening_balance'))
        write_row(_('Aumento neto en efectivo'), data.get('net_increase'))
        for sec_key, sec in (data.get('sections') or {}).items():
            if not isinstance(sec, dict):
                continue
            write_row(sec.get('name') or sec_key, sec.get('total'))
            for sub_key, sub in (sec.get('subsections') or {}).items():
                if not isinstance(sub, dict):
                    continue
                write_row('  ' + (sub.get('name') or sub_key), sub.get('total'))
                for acc in sub.get('accounts') or []:
                    if isinstance(acc, dict):
                        write_row(
                            '    %s %s' % (acc.get('code') or '', acc.get('name') or ''),
                            acc.get('balance'),
                        )
        write_row(_('Efectivo y equivalentes, saldo final'), data.get('closing_balance'))
        if data.get('unexplained_difference'):
            write_row(_('Diferencia no explicada'), data.get('unexplained_difference'))

        workbook.close()
        buf.seek(0)
        return {
            'excel_file': base64.b64encode(buf.read()).decode('utf-8'),
            'file_name': 'Cash_flow.xlsx',
        }

    @api.model
    def action_open_aml(self, options, account_id):
        opts = dict(options or {})
        helper = self.env["bi.report.drilldown.helper"]
        domain = helper.aml_domain(opts, account_id=int(account_id))
        return helper.action_aml_window(domain)

    def _finalize_result(self, date_from, date_to, currency_data, sections,
                         opening_accounts, closing_accounts,
                         opening_total, closing_total, has_draft_warning):
        # Convertir 'accounts' de dict a list ordenada por code.
        for sec in sections.values():
            for sub in sec['subsections'].values():
                accounts = list(sub['accounts'].values())
                accounts.sort(key=lambda a: (a.get('code') or '', a.get('name') or ''))
                sub['accounts'] = accounts

        net_increase = sum(s['total'] for s in sections.values())
        unexplained = closing_total - opening_total - net_increase
        if self.env.company.currency_id.is_zero(unexplained):
            unexplained = 0.0

        return {
            'date_from': fields.Date.to_string(date_from),
            'date_to': fields.Date.to_string(date_to),
            'company': self.env.company.name,
            'currency_data': currency_data,
            'opening_balance': opening_total,
            'closing_balance': closing_total,
            'net_increase': net_increase,
            'unexplained_difference': unexplained,
            'opening_accounts': sorted(opening_accounts.values(), key=lambda a: (a.get('code') or '', a.get('name') or '')),
            'closing_accounts': sorted(closing_accounts.values(), key=lambda a: (a.get('code') or '', a.get('name') or '')),
            'sections': sections,
            'has_draft_warning': has_draft_warning,
        }
