# -*- coding: utf-8 -*-
"""Datos compartidos Excel + informe HTML (QWeb) balance semanal bancarios."""
from datetime import date, timedelta

from odoo import _, api, fields, models




class BanksWeeklyBalanceCommon(models.AbstractModel):
    _name = 'banks.weekly.balance.common'
    _description = 'Cálculos informe balance bancario semanal (Excel / QWeb)'

    def _translated_month_name(self, month_number):
        """Return the translated month name for ``month_number`` (1-12).

        Implemented as instance method (instead of module-level) so that
        Odoo's translation machinery can detect ``self.env`` and resolve
        the active language without emitting "no translation language
        detected" warnings.
        """
        names = (
            _('Enero'),
            _('Febrero'),
            _('Marzo'),
            _('Abril'),
            _('Mayo'),
            _('Junio'),
            _('Julio'),
            _('Agosto'),
            _('Septiembre'),
            _('Octubre'),
            _('Noviembre'),
            _('Diciembre'),
        )
        idx = max(1, min(12, int(month_number or 1))) - 1
        return names[idx]

    # Tipos de diario elegibles para el dashboard de balances. La inclusión
    # real está controlada por el flag ``gn_include_in_balance_dashboard``
    # (por defecto desactivado), por lo que añadir 'cash' es retrocompatible:
    # sólo aparece un diario de caja si un administrador lo marca expresamente.
    _BALANCE_JOURNAL_TYPES = ('bank', 'cash')

    @api.model
    def _balance_journal_domain(self, company_id):
        """Diarios banco/caja visibles en el informe (sólo los marcados)."""
        domain = [
            ('type', 'in', list(self._BALANCE_JOURNAL_TYPES)),
            ('company_id', '=', company_id),
            ('gn_include_in_balance_dashboard', '=', True),
        ]
        return domain

    @api.model
    def search_balance_journals(self, company_id, journal_ids=None):
        domain = self._balance_journal_domain(company_id)
        if journal_ids:
            domain.append(('id', 'in', journal_ids))
        return self.env['account.journal'].search(domain, order='name')

    def _ml_domain_base(self, company, account_ids):
        return [
            ('company_id', 'child_of', company.id),
            ('account_id', 'in', list(account_ids)),
            (
                'display_type',
                'not in',
                ('line_section', 'line_subsection', 'line_note'),
            ),
            ('parent_state', '=', 'posted'),
        ]

    def _sums_through_date(self, company, account_ids_set, upto):
        if not account_ids_set:
            return {}
        aml = self.env['account.move.line']
        agg = aml._read_group(
            domain=self._ml_domain_base(company, account_ids_set)
                + [('date', '<=', upto)],
            groupby=['account_id'],
            aggregates=['balance:sum'],
        )
        return {gid.id: float(val or 0.0) for gid, val in agg}

    def _period_debit_credit(self, company, account_ids_set, d_from, d_to):
        if not account_ids_set:
            return {}, {}
        aml = self.env['account.move.line']
        domain = self._ml_domain_base(company, account_ids_set)
        domain += [('date', '>=', d_from), ('date', '<=', d_to)]
        deb = aml._read_group(
            domain=domain,
            groupby=['account_id'],
            aggregates=['debit:sum'],
        )
        cre = aml._read_group(
            domain=domain,
            groupby=['account_id'],
            aggregates=['credit:sum'],
        )
        return (
            {gid.id: float(v or 0.0) for gid, v in deb},
            {gid.id: float(v or 0.0) for gid, v in cre},
        )

    def _collect_period_buckets(self, company, account_ids_set, ranges):
        """Compute per-bucket opening/inflow/outflow plus end balance with 2 queries.

        Returns a dict:
            {
                'base_balance': {aid: float},     # saldo a (period_start - 1)
                'end_balance':  {aid: float},     # saldo a period_end (último bucket)
                'agg_debit':    {aid: float},     # totales débito del periodo
                'agg_credit':   {aid: float},     # totales crédito del periodo
                'buckets': {
                    week_no: {
                        'opening': {aid: float},
                        'inflow':  {aid: float},
                        'outflow': {aid: float},
                        'final':   {aid: float},
                    },
                    ...
                },
            }
        """
        if not account_ids_set or not ranges:
            return {
                'base_balance': {},
                'end_balance': {},
                'agg_debit': {},
                'agg_credit': {},
                'buckets': {},
            }
        period_start = ranges[0][1]
        period_end = ranges[-1][2]

        base_balance = self._sums_through_date(
            company, account_ids_set, period_start - timedelta(days=1),
        )

        aml = self.env['account.move.line']
        movements = aml._read_group(
            domain=self._ml_domain_base(company, account_ids_set)
                + [('date', '>=', period_start), ('date', '<=', period_end)],
            groupby=['account_id', 'date:day'],
            aggregates=['debit:sum', 'credit:sum'],
        )

        daily = {aid: {} for aid in account_ids_set}
        for account, day, deb, cred in movements:
            if hasattr(day, 'date'):
                day = day.date()
            if account.id in daily:
                daily[account.id][day] = (
                    float(deb or 0.0),
                    float(cred or 0.0),
                )

        cumulative_net = {aid: 0.0 for aid in account_ids_set}
        agg_debit = {aid: 0.0 for aid in account_ids_set}
        agg_credit = {aid: 0.0 for aid in account_ids_set}
        buckets = {}
        for week_no, w_start, w_end in ranges:
            opening = {
                aid: base_balance.get(aid, 0.0) + cumulative_net[aid]
                for aid in account_ids_set
            }
            inflow = {aid: 0.0 for aid in account_ids_set}
            outflow = {aid: 0.0 for aid in account_ids_set}
            for aid in account_ids_set:
                for day, (deb, cred) in daily[aid].items():
                    if w_start <= day <= w_end:
                        inflow[aid] += deb
                        outflow[aid] += cred
                        cumulative_net[aid] += deb - cred
                agg_debit[aid] += inflow[aid]
                agg_credit[aid] += outflow[aid]
            final = {
                aid: opening[aid] + inflow[aid] - outflow[aid]
                for aid in account_ids_set
            }
            buckets[week_no] = {
                'opening': opening,
                'inflow': inflow,
                'outflow': outflow,
                'final': final,
            }

        end_balance = {
            aid: base_balance.get(aid, 0.0) + cumulative_net[aid]
            for aid in account_ids_set
        }
        return {
            'base_balance': base_balance,
            'end_balance': end_balance,
            'agg_debit': agg_debit,
            'agg_credit': agg_credit,
            'buckets': buckets,
        }

    def _build_kpis(self, journals, agg_debit, agg_credit, end_bal, account_ids_set,
                    compare_kpis=None, company=None):
        """KPIs agregados en la moneda de la company.

        Notas multi-moneda:
            - ``account.move.line.balance/debit/credit`` ya están expresados
              en la moneda de la company (Odoo aplica la conversión al postear).
            - Se redondea con ``company.currency_id`` para evitar drift de
              sumatorios de saldos provenientes de cuentas distintas.
            - ``mixed_currency`` indica si alguno de los diarios usa una
              moneda distinta a la company; el frontend puede usarlo para
              mostrar advertencia al usuario.
        """
        currency = (company.currency_id if company else None)
        round_amt = currency.round if currency else (lambda v: v)

        total_in = round_amt(sum(agg_debit.get(aid, 0.0) for aid in account_ids_set))
        total_out = round_amt(sum(agg_credit.get(aid, 0.0) for aid in account_ids_set))
        end_tot = round_amt(sum(end_bal.get(aid, 0.0) for aid in account_ids_set))
        net_flow = round_amt(total_in - total_out)

        top_bal_j = journals[0]
        top_bal_amt = 0.0
        top_mov_j = journals[0]
        top_mov_amt = 0.0
        mixed_currency = False
        foreign_currency_journals = []
        for j in journals:
            aid = j.default_account_id.id
            bal = round_amt(end_bal.get(aid, 0.0))
            mov = round_amt(agg_debit.get(aid, 0.0) + agg_credit.get(aid, 0.0))
            if bal >= top_bal_amt:
                top_bal_amt = bal
                top_bal_j = j
            if mov >= top_mov_amt:
                top_mov_amt = mov
                top_mov_j = j
            if currency and j.currency_id and j.currency_id != currency:
                mixed_currency = True
                foreign_currency_journals.append({
                    'journal_id': j.id,
                    'name': j.name or '',
                    'currency_id': j.currency_id.id,
                    'currency_name': j.currency_id.name,
                })

        kpis = {
            'total_balance': end_tot,
            'total_inflows': total_in,
            'total_outflows': total_out,
            'net_flow': net_flow,
            'top_balance_bank': {
                'name': top_bal_j.name or '',
                'journal_id': top_bal_j.id,
                'amount': top_bal_amt,
            },
            'top_movement_bank': {
                'name': top_mov_j.name or '',
                'journal_id': top_mov_j.id,
                'amount': top_mov_amt,
            },
            'currency_id': currency.id if currency else False,
            'mixed_currency': mixed_currency,
            'foreign_currency_journals': foreign_currency_journals,
        }
        if compare_kpis:
            kpis['compare'] = {
                'total_balance_delta': round_amt(
                    end_tot - compare_kpis.get('total_balance', 0.0)
                ),
                'total_inflows_delta': round_amt(
                    total_in - compare_kpis.get('total_inflows', 0.0)
                ),
                'total_outflows_delta': round_amt(
                    total_out - compare_kpis.get('total_outflows', 0.0)
                ),
                'net_flow_delta': round_amt(
                    net_flow - compare_kpis.get('net_flow', 0.0)
                ),
            }
        return kpis

    def _build_charts(self, journals, week_blocks, agg_debit, agg_credit, end_bal):
        # Resolve translation outside the listcomp so Odoo's translate
        # heuristic can find ``self`` (listcomps own their frame and would
        # trigger "no translation language detected" warnings otherwise).
        week_label_tpl = _('S%(n)s')
        week_labels = [
            week_label_tpl % {'n': wb.get('week_no', idx + 1)}
            for idx, wb in enumerate(week_blocks)
        ]
        inflows = []
        outflows = []
        net_flow = []
        opening_totals = []
        for wb in week_blocks:
            in_row = next((r for r in wb['rows'] if r['row_type'] == 'inflow'), None)
            out_row = next((r for r in wb['rows'] if r['row_type'] == 'outflow'), None)
            op_row = next((r for r in wb['rows'] if r['row_type'] == 'opening'), None)
            inflows.append(in_row['total'] if in_row else 0.0)
            outflows.append(out_row['total'] if out_row else 0.0)
            net_flow.append(inflows[-1] - outflows[-1])
            opening_totals.append(op_row['total'] if op_row else 0.0)

        bank_labels = [(j.name or '')[:24] for j in journals]
        bank_inflows = [agg_debit.get(j.default_account_id.id, 0.0) for j in journals]
        bank_outflows = [agg_credit.get(j.default_account_id.id, 0.0) for j in journals]
        bank_balances = [end_bal.get(j.default_account_id.id, 0.0) for j in journals]

        evolution_datasets = []
        for col_idx, j in enumerate(journals):
            series = []
            for wb in week_blocks:
                op_row = next((r for r in wb['rows'] if r['row_type'] == 'opening'), None)
                series.append(
                    op_row['amounts'][col_idx] if op_row and col_idx < len(op_row['amounts']) else 0.0
                )
            evolution_datasets.append({
                'label': (j.name or '')[:20],
                'journal_id': j.id,
                'data': series,
            })

        return {
            'weekly_flow': {
                'labels': week_labels,
                'inflows': inflows,
                'outflows': outflows,
                'net': net_flow,
            },
            'bank_comparison': {
                'labels': bank_labels,
                'inflows': bank_inflows,
                'outflows': bank_outflows,
                'balances': bank_balances,
            },
            'balance_evolution': {
                'labels': week_labels,
                'datasets': evolution_datasets,
                'totals': opening_totals,
            },
            'distribution': {
                'labels': bank_labels,
                'values': bank_balances,
            },
        }

    @api.model
    def resolve_period_and_ranges(self, wizard, group_by='week'):
        """Period bounds and bucket ranges for wizard filters."""
        if wizard.date_from and wizard.date_to:
            period_start, period_end = wizard.date_from, wizard.date_to
        else:
            month = int(wizard.month)
            import calendar as cal_mod
            last_day = cal_mod.monthrange(int(wizard.year), month)[1]
            period_start = date(int(wizard.year), month, 1)
            period_end = date(int(wizard.year), month, last_day)
        if group_by == 'week' and not (wizard.date_from and wizard.date_to):
            return wizard._month_week_ranges()
        return self._period_bucket_ranges(period_start, period_end, group_by)

    @api.model
    def _period_bucket_ranges(self, period_start, period_end, group_by='week'):
        """Calendar buckets: week (7d), fortnight (15d), or month."""
        if period_start > period_end:
            period_start, period_end = period_end, period_start
        if group_by == 'month':
            ranges = []
            bucket_no = 1
            cursor_date = period_start
            while cursor_date <= period_end:
                if cursor_date.month == period_end.month and cursor_date.year == period_end.year:
                    w_end = period_end
                else:
                    import calendar as cal_mod
                    last = cal_mod.monthrange(cursor_date.year, cursor_date.month)[1]
                    w_end = date(cursor_date.year, cursor_date.month, last)
                    if w_end > period_end:
                        w_end = period_end
                ranges.append((bucket_no, cursor_date, w_end))
                bucket_no += 1
                cursor_date = w_end + timedelta(days=1)
            return period_start, period_end, ranges
        step = 15 if group_by == 'fortnight' else 7
        ranges = []
        bucket_no = 1
        cursor_date = period_start
        while cursor_date <= period_end:
            w_end = min(cursor_date + timedelta(days=step - 1), period_end)
            ranges.append((bucket_no, cursor_date, w_end))
            bucket_no += 1
            cursor_date = w_end + timedelta(days=1)
        return period_start, period_end, ranges

    def _round2(self, value):
        return round(float(value or 0.0), 2)

    @api.model
    def _week_short_key(self, week_no):
        return 'S%s' % (week_no or 0)

    def _fetch_bucket_metrics(self, company, account_ids, buckets):
        """Movement count and largest movement per account per bucket.

        Uses a single grouped query (``account_id`` x ``date:day``) instead of
        loading every journal item into Python, so cost scales with
        accounts x days (bounded) rather than with the number of postings.

        ``movement_count`` is the exact number of journal items.
        ``largest_movement`` is the largest absolute net movement of a single
        day (the biggest daily swing); for the typical case of one posting per
        day on a liquidity account this equals the largest single movement.
        """
        if not account_ids or not buckets:
            return {}
        aml = self.env['account.move.line']
        period_start = buckets[0][1]
        period_end = buckets[-1][2]

        bucket_by_date = {}
        for bucket_no, d_from, d_to in buckets:
            cursor_date = d_from
            while cursor_date <= d_to:
                bucket_by_date[cursor_date] = bucket_no
                cursor_date += timedelta(days=1)

        metrics = {
            (bucket_no, aid): {
                'movement_count': 0,
                'largest_movement': 0.0,
            }
            for bucket_no, _d_from, _d_to in buckets
            for aid in account_ids
        }
        rows = aml._read_group(
            domain=self._ml_domain_base(company, account_ids)
            + [('date', '>=', period_start), ('date', '<=', period_end)],
            groupby=['account_id', 'date:day'],
            aggregates=['__count', 'debit:sum', 'credit:sum'],
        )
        for account, day, count, debit, credit in rows:
            if hasattr(day, 'date'):
                day = day.date()
            bucket_no = bucket_by_date.get(day)
            if bucket_no is None:
                continue
            key = (bucket_no, account.id)
            if key not in metrics:
                continue
            metrics[key]['movement_count'] += int(count or 0)
            swing = abs(float(debit or 0.0) - float(credit or 0.0))
            if swing > metrics[key]['largest_movement']:
                metrics[key]['largest_movement'] = swing
        return metrics

    def _build_weeks_summary(self, week_blocks, journals, metrics):
        weeks = []
        prev_final = None
        for wb in week_blocks:
            in_row = next((r for r in wb['rows'] if r['row_type'] == 'inflow'), None)
            out_row = next((r for r in wb['rows'] if r['row_type'] == 'outflow'), None)
            op_row = next((r for r in wb['rows'] if r['row_type'] == 'opening'), None)
            opening = self._round2(op_row['total'] if op_row else 0.0)
            inflows = self._round2(in_row['total'] if in_row else 0.0)
            outflows = self._round2(out_row['total'] if out_row else 0.0)
            net_flow = self._round2(inflows - outflows)
            final_balance = self._round2(opening + net_flow)
            diff_prev = self._round2(
                final_balance - prev_final if prev_final is not None else 0.0
            )
            banks = []
            main_bank = ''
            main_mov = -1.0
            for idx, j in enumerate(journals):
                aid = j.default_account_id.id
                bno = wb.get('week_no', 0)
                m = metrics.get((bno, aid), {})
                b_in = self._round2(
                    in_row['amounts'][idx] if in_row and idx < len(in_row['amounts']) else 0.0
                )
                b_out = self._round2(
                    out_row['amounts'][idx] if out_row and idx < len(out_row['amounts']) else 0.0
                )
                b_open = self._round2(
                    op_row['amounts'][idx] if op_row and idx < len(op_row['amounts']) else 0.0
                )
                b_net = self._round2(b_in - b_out)
                b_final = self._round2(b_open + b_net)
                mov = b_in + b_out
                if mov > main_mov:
                    main_mov = mov
                    main_bank = j.name or ''
                banks.append({
                    'bank_id': j.bank_id.id if j.bank_id else False,
                    'bank_name': j.name or '',
                    'journal_id': j.id,
                    'account_id': aid,
                    'initial_balance': b_open,
                    'inflows': b_in,
                    'outflows': b_out,
                    'net_flow': b_net,
                    'final_balance': b_final,
                    'largest_movement': self._round2(m.get('largest_movement', 0.0)),
                    'movement_count': m.get('movement_count', 0),
                })
            week_no = wb.get('week_no', 0)
            movement_count = sum(b.get('movement_count', 0) for b in banks)
            weeks.append({
                'key': self._week_short_key(week_no),
                'week_no': week_no,
                'label': _('Semana %(n)s') % {'n': week_no},
                'period_label': wb.get('period_label', ''),
                'date_from': wb.get('date_from'),
                'date_to': wb.get('date_to'),
                'initial_balance': opening,
                'inflows': inflows,
                'outflows': outflows,
                'net_flow': net_flow,
                'final_balance': final_balance,
                'difference_previous_week': diff_prev,
                'main_bank': main_bank,
                'movement_count': movement_count,
                'banks': banks,
            })
            prev_final = final_balance
        return weeks

    def _build_kpis_v2(self, weeks, initial_balance, final_balance, journals,
                       agg_debit, agg_credit, account_ids_set, compare=None,
                       company=None):
        """KPIs v2 normalizados a moneda de la company.

        Ver ``_build_kpis`` para la nota multi-moneda.
        """
        currency = (company.currency_id if company else None)
        round_amt = currency.round if currency else (lambda v: v)

        total_in = sum(agg_debit.get(aid, 0.0) for aid in account_ids_set)
        total_out = sum(agg_credit.get(aid, 0.0) for aid in account_ids_set)
        net = total_in - total_out
        avg_liq = (
            sum(w['final_balance'] for w in weeks) / len(weeks) if weeks else 0.0
        )
        ratio = (total_in / total_out * 100.0) if total_out > 0 else None
        critical = min(weeks, key=lambda w: w['final_balance']) if weeks else {}
        top_mov_j = journals[0]
        top_mov = 0.0
        mixed_currency = False
        foreign_currency_journals = []
        for j in journals:
            aid = j.default_account_id.id
            mov = agg_debit.get(aid, 0.0) + agg_credit.get(aid, 0.0)
            if mov >= top_mov:
                top_mov = mov
                top_mov_j = j
            if currency and j.currency_id and j.currency_id != currency:
                mixed_currency = True
                foreign_currency_journals.append({
                    'journal_id': j.id,
                    'name': j.name or '',
                    'currency_id': j.currency_id.id,
                    'currency_name': j.currency_id.name,
                })
        variation = None
        if initial_balance:
            variation = ((final_balance - initial_balance) / abs(initial_balance)) * 100.0
        crit_val = round_amt(self._round2(critical.get('final_balance', 0.0)))
        top_bank_amount = round_amt(self._round2(top_mov))
        avg_liq_r = round_amt(self._round2(avg_liq))
        variation_r = self._round2(variation) if variation is not None else None
        kpis = {
            'initial_balance': round_amt(self._round2(initial_balance)),
            'final_balance': round_amt(self._round2(final_balance)),
            'total_inflows': round_amt(self._round2(total_in)),
            'total_outflows': round_amt(self._round2(total_out)),
            'net_flow': round_amt(self._round2(net)),
            'total_balance': round_amt(self._round2(final_balance)),
            'critical_week': {
                'label': critical.get('label') or critical.get('period_label', ''),
                'week_no': critical.get('week_no'),
                'week_key': critical.get('key'),
                'final_balance': crit_val,
                'value': crit_val,
            },
            'top_bank': {
                'name': top_mov_j.name or '',
                'journal_id': top_mov_j.id,
                'amount': top_bank_amount,
                'value': top_bank_amount,
            },
            'main_bank': {
                'name': top_mov_j.name or '',
                'journal_id': top_mov_j.id,
                'amount': top_bank_amount,
                'value': top_bank_amount,
            },
            'top_movement_bank': {
                'name': top_mov_j.name or '',
                'journal_id': top_mov_j.id,
                'amount': top_bank_amount,
            },
            'income_expense_ratio': self._round2(ratio) if ratio is not None else None,
            'average_weekly_liquidity': avg_liq_r,
            'average_liquidity': avg_liq_r,
            'variation_previous_period': variation_r,
            'variation_period': variation_r,
            'currency_id': currency.id if currency else False,
            'mixed_currency': mixed_currency,
            'foreign_currency_journals': foreign_currency_journals,
        }
        if compare:
            kpis['compare'] = compare
        return kpis

    def _build_insights(self, weeks, kpis, journals, agg_debit, agg_credit, account_ids_set):
        insights = []
        if not weeks:
            return insights

        def _ins(category, severity, title, message, value=None, icon='fa-info-circle'):
            insights.append({
                'category': category,
                'severity': severity,
                'type': severity,
                'title': title,
                'message': message,
                'value': self._round2(value) if value is not None else None,
                'icon': icon,
            })

        critical = kpis.get('critical_week') or {}
        if critical.get('week_no'):
            _ins(
                _('Liquidez'),
                'warning',
                _('Semana crítica'),
                _('La %(label)s fue la semana crítica con saldo final de %(amount)s.') % {
                    'label': critical.get('label') or critical.get('week_key', ''),
                    'amount': critical.get('value', 0.0),
                },
                critical.get('value'),
                'fa-exclamation-triangle',
            )

        top_bank = kpis.get('main_bank') or kpis.get('top_bank') or {}
        if top_bank.get('name'):
            _ins(
                _('Concentración bancaria'),
                'info',
                _('Banco principal'),
                _('El banco %(bank)s concentró el mayor movimiento del período (%(amount)s).') % {
                    'bank': top_bank.get('name'),
                    'amount': top_bank.get('value', 0.0),
                },
                top_bank.get('value'),
                'fa-university',
            )

        ratio = kpis.get('income_expense_ratio')
        if ratio is not None:
            _ins(
                _('Cobertura'),
                'success' if ratio >= 100 else 'warning',
                _('Cobertura ingresos/salidas'),
                _('Los ingresos cubrieron el %(pct).2f%% de las salidas.') % {'pct': ratio},
                ratio,
                'fa-percent',
            )

        variation = kpis.get('variation_period')
        if variation is not None:
            _ins(
                _('Tendencia'),
                'success' if variation >= 0 else 'danger',
                _('Variación del período'),
                _('El saldo final %(dir)s %(pct).2f%% respecto al saldo inicial.') % {
                    'dir': _('mejoró') if variation >= 0 else _('cayó'),
                    'pct': abs(variation),
                },
                variation,
                'fa-line-chart',
            )

        net = kpis.get('net_flow') or 0.0
        if net < 0:
            _ins(
                _('Riesgo'),
                'danger',
                _('Flujo neto negativo'),
                _('El flujo neto del período fue negativo (%(amount)s).') % {'amount': net},
                net,
                'fa-arrow-down',
            )

        max_growth = max(weeks, key=lambda w: w.get('net_flow', 0.0))
        if max_growth.get('net_flow', 0.0) > 0:
            _ins(
                _('Tendencia'),
                'success',
                _('Mayor crecimiento de caja'),
                _('La %(label)s generó el mayor crecimiento de caja (%(amount)s).') % {
                    'label': max_growth.get('label'),
                    'amount': max_growth.get('net_flow'),
                },
                max_growth.get('net_flow'),
                'fa-arrow-up',
            )

        max_out_w = max(weeks, key=lambda w: w.get('outflows', 0.0))
        if max_out_w.get('outflows', 0.0) > 0:
            _ins(
                _('Riesgo'),
                'warning',
                _('Semana con mayor egreso'),
                _('%(period)s concentró el mayor egreso del período.') % {
                    'period': max_out_w.get('period_label') or max_out_w.get('label'),
                },
                max_out_w.get('outflows'),
                'fa-minus-circle',
            )

        return insights

    def _build_waterfall_steps(self, weeks, initial_balance):
        """Rich waterfall payload with short labels and running balances."""
        running = float(initial_balance)
        steps = [{
            'label': _('Saldo inicial'),
            'short_label': _('Inicial'),
            'type': 'initial',
            'amount': self._round2(initial_balance),
            'value': self._round2(initial_balance),
            'running_balance': self._round2(running),
            'movement_type': _('Saldo'),
        }]
        for w in weeks:
            week_key = w.get('key') or self._week_short_key(w.get('week_no'))
            week_label = w.get('label') or week_key
            date_from = w.get('date_from')
            date_to = w.get('date_to')
            if w.get('inflows'):
                running += w['inflows']
                steps.append({
                    'label': _('%s ingresos') % week_label,
                    'short_label': _('%s ing.') % week_key,
                    'type': 'inflow',
                    'week_key': week_key,
                    'week_no': w.get('week_no'),
                    'date_from': date_from,
                    'date_to': date_to,
                    'amount': self._round2(w['inflows']),
                    'value': self._round2(w['inflows']),
                    'running_balance': self._round2(running),
                    'movement_type': _('Ingresos'),
                })
            if w.get('outflows'):
                running -= w['outflows']
                steps.append({
                    'label': _('%s salidas') % week_label,
                    'short_label': _('%s sal.') % week_key,
                    'type': 'outflow',
                    'week_key': week_key,
                    'week_no': w.get('week_no'),
                    'date_from': date_from,
                    'date_to': date_to,
                    'amount': self._round2(-w['outflows']),
                    'value': self._round2(-w['outflows']),
                    'running_balance': self._round2(running),
                    'movement_type': _('Salidas'),
                })
            steps.append({
                'label': week_label,
                'short_label': week_key,
                'type': 'subtotal',
                'week_key': week_key,
                'week_no': w.get('week_no'),
                'date_from': date_from,
                'date_to': date_to,
                'amount': self._round2(running),
                'value': self._round2(running),
                'running_balance': self._round2(running),
                'movement_type': _('Saldo acumulado'),
            })
        steps.append({
            'label': _('Saldo final'),
            'short_label': _('Final'),
            'type': 'final',
            'amount': self._round2(running),
            'value': self._round2(running),
            'running_balance': self._round2(running),
            'movement_type': _('Saldo'),
        })
        return steps

    def _build_chart_series_v2(self, weeks, journals, end_bal, agg_debit, agg_credit):
        labels = [w['label'] for w in weeks]
        week_keys = [w.get('key') or self._week_short_key(w.get('week_no')) for w in weeks]
        date_ranges = [
            {'from': w['date_from'], 'to': w['date_to']} for w in weeks
        ]
        inflows = [w['inflows'] for w in weeks]
        outflows = [w['outflows'] for w in weeks]
        net = [w['net_flow'] for w in weeks]
        opening = [w['initial_balance'] for w in weeks]
        closing = [w['final_balance'] for w in weeks]
        diff_prev = [w['difference_previous_week'] for w in weeks]
        min_w = min(weeks, key=lambda w: w['final_balance']) if weeks else {}
        max_w = max(weeks, key=lambda w: w['final_balance']) if weeks else {}
        avg_balance = (
            sum(closing) / len(closing) if closing else 0.0
        )
        avg_line = [self._round2(avg_balance)] * len(weeks) if weeks else []
        bank_labels = [(j.name or '')[:24] for j in journals]
        return {
            'cashflow': {
                'labels': labels,
                'week_keys': week_keys,
                'date_ranges': date_ranges,
                'inflows': inflows,
                'outflows': outflows,
                'net': net,
                'closing': closing,
                'negative_weeks': [
                    week_keys[i] for i, v in enumerate(net) if v < 0
                ],
            },
            'balance_evolution': {
                'labels': labels,
                'week_keys': week_keys,
                'date_ranges': date_ranges,
                'opening': opening,
                'closing': closing,
                'average': avg_line,
                'diff_previous': diff_prev,
                'min_week': min_w.get('week_no'),
                'min_week_key': min_w.get('key'),
                'max_week': max_w.get('week_no'),
                'max_week_key': max_w.get('key'),
                'min_balance': min_w.get('final_balance'),
                'max_balance': max_w.get('final_balance'),
            },
            'bank_comparison': {
                'labels': bank_labels,
                'inflows': [self._round2(agg_debit.get(j.default_account_id.id, 0.0)) for j in journals],
                'outflows': [self._round2(agg_credit.get(j.default_account_id.id, 0.0)) for j in journals],
                'balances': [self._round2(end_bal.get(j.default_account_id.id, 0.0)) for j in journals],
            },
            'distribution': {
                'labels': bank_labels,
                'values': [self._round2(end_bal.get(j.default_account_id.id, 0.0)) for j in journals],
            },
        }

    def build_dashboard_payload(self, wizard, options=None):
        """Full dashboard JSON for OWL (includes legacy keys for exports)."""
        options = options or {}
        group_by = options.get('group_by', 'week')
        payload = self.build_payload(wizard, {**options, '_group_by': group_by})
        if not payload.get('has_data'):
            payload.setdefault('period', {})
            payload.setdefault('weeks', [])
            payload.setdefault('insights', [])
            payload.setdefault('currency', {})
            return payload

        company = wizard.company_id
        journals = self.search_balance_journals(
            company.id, wizard.journal_ids.ids
        ).filtered('default_account_id').sorted(key=lambda j: j.name or '')
        account_ids_set = journals.mapped('default_account_id').ids
        period_start, period_end, bucket_ranges = self.resolve_period_and_ranges(
            wizard, group_by,
        )

        aggregations = payload.get('_aggregations') or self._collect_period_buckets(
            company, account_ids_set, bucket_ranges,
        )
        initial_bal_map = aggregations.get('base_balance', {})
        initial_balance = sum(
            initial_bal_map.get(aid, 0.0) for aid in account_ids_set
        )
        end_bal = aggregations.get('end_balance', {})
        final_balance = sum(end_bal.get(aid, 0.0) for aid in account_ids_set)
        agg_debit = dict(aggregations.get('agg_debit') or {})
        agg_credit = dict(aggregations.get('agg_credit') or {})
        for aid in account_ids_set:
            agg_debit.setdefault(aid, 0.0)
            agg_credit.setdefault(aid, 0.0)

        # Light mode (e.g. Salud financiera tab): the consumer only needs
        # weeks + KPIs + aggregations, so skip the per-bucket metric query and
        # the pure-presentation chart/insight/waterfall builders.
        light = options.get('_light')
        metrics = (
            {} if light
            else self._fetch_bucket_metrics(company, account_ids_set, bucket_ranges)
        )
        weeks = self._build_weeks_summary(payload['week_blocks'], journals, metrics)

        compare = payload.get('kpis', {}).get('compare')
        kpis_v2 = self._build_kpis_v2(
            weeks, initial_balance, final_balance, journals,
            agg_debit, agg_credit, account_ids_set, compare,
            company=company,
        )
        if light:
            insights = []
            waterfall_steps = []
            charts_v2 = {}
        else:
            insights = self._build_insights(
                weeks, kpis_v2, journals, agg_debit, agg_credit, account_ids_set,
            )
            waterfall_steps = self._build_waterfall_steps(weeks, initial_balance)
            charts_v2 = self._build_chart_series_v2(
                weeks, journals, end_bal, agg_debit, agg_credit,
            )
            charts_v2['waterfall'] = {'steps': waterfall_steps}
        currency = company.currency_id
        payload.update({
            'period': {
                'date_from': period_start.isoformat(),
                'date_to': period_end.isoformat(),
                'label': payload.get('month_year_title', ''),
                'comparison_enabled': bool(options.get('compare_previous')),
                'group_by': group_by,
            },
            'currency': {
                'id': currency.id,
                'symbol': currency.symbol or currency.name or '',
                'position': currency.position or 'before',
                'decimal_places': currency.decimal_places,
            },
            'weeks': weeks,
            'waterfall': waterfall_steps,
            'insights': insights,
            'kpis': kpis_v2,
            'charts': {**payload.get('charts', {}), **charts_v2},
        })
        return payload

    def build_legacy_payload(self, wizard, options=None):
        return self.build_dashboard_payload(wizard, options)

    def _previous_period_wizard(self, wizard):
        month = int(wizard.month)
        year = int(wizard.year)
        if month == 1:
            prev_month, prev_year = 12, year - 1
        else:
            prev_month, prev_year = month - 1, year
        # In-memory record: only read for the comparison payload, never stored.
        return self.env['banks.weekly.balance.report'].new({
            'company_id': wizard.company_id.id,
            'year': prev_year,
            'month': str(prev_month),
            'journal_ids': [(6, 0, wizard.journal_ids.ids)],
        })

    def build_payload(self, wizard, options=None):
        wizard.ensure_one()
        options = options or {}
        company = wizard.company_id
        allowed = self.search_balance_journals(company.id, wizard.journal_ids.ids)
        journals = allowed.filtered(lambda j: j.default_account_id)
        journals = journals.sorted(lambda j: j.name or '')
        currency = company.currency_id
        symbol = currency.symbol or currency.name or ''
        month_name = self._translated_month_name(wizard.month)

        subtitle_txt = _(
                'Balance semanal por banco por mes '
                '(bloques de hasta 7 días dentro del mes calendario)'
        )
        empty = {
            'has_data': False,
            'error_message': _(
                'No hay diarios de banco marcados para Balances con cuenta '
                'de liquidez por defecto.'
            ),
            'journal_columns': [],
            'week_blocks': [],
            'summary_lines': [],
            'company_name': wizard.company_id.name or '',
            'month_year_title': '%s %s' % (month_name, wizard.year),
            'currency_symbol': symbol,
            'currency_id': currency.id,
            'subtitle': subtitle_txt,
            'month_end_str': '',
            'kpis': {},
            'charts': {},
            'generated_at': fields.Datetime.now().isoformat(),
        }

        if not journals:
            return empty

        account_ids_set = journals.mapped('default_account_id').ids
        group_by = options.get('_group_by', 'week')
        period_start, month_end, ranges = self.resolve_period_and_ranges(
            wizard, group_by,
        )

        journal_columns = []
        for j in journals:
            lbl = (
                '%s (%s)'
                % (j.bank_id.name or '', j.bank_acc_number or (j.name or '')[:28])
                if j.bank_id
                else ((j.name or '')[:42])
            )
            journal_columns.append({
                'label': lbl,
                'journal_id': j.id,
                'account_id': j.default_account_id.id,
                'color_index': len(journal_columns) % 8,
            })

        aggregations = self._collect_period_buckets(
            company, account_ids_set, ranges,
        )
        agg_debit = aggregations['agg_debit']
        agg_credit = aggregations['agg_credit']
        bucket_data = aggregations['buckets']
        end_bal = aggregations['end_balance']
        prev_total_ini = None
        week_blocks = []

        for week_no, w_start, w_end in ranges:
            bucket = bucket_data.get(week_no, {})
            opening_map = bucket.get('opening', {})
            inflow_map = bucket.get('inflow', {})
            outflow_map = bucket.get('outflow', {})

            period_label = _(
                'Semana %(n)s: del %(di)s al %(df)s'
            ) % {
                'n': week_no,
                'di': w_start.strftime('%d/%m/%Y'),
                'df': w_end.strftime('%d/%m/%Y'),
            }

            cells_ini = []
            total_ini = 0.0
            for j in journals:
                aid = j.default_account_id.id
                v = opening_map.get(aid, 0.0)
                cells_ini.append(v)
                total_ini += v

            delta_val = (
                total_ini - prev_total_ini if prev_total_ini is not None else 0.0
            )
            prev_total_ini = total_ini

            cells_deb = []
            total_deb = 0.0
            for j in journals:
                aid = j.default_account_id.id
                dv = inflow_map.get(aid, 0.0)
                cells_deb.append(dv)
                total_deb += dv

            cells_cred = []
            total_cred = 0.0
            for j in journals:
                aid = j.default_account_id.id
                cv = outflow_map.get(aid, 0.0)
                cells_cred.append(cv)
                total_cred += cv

            week_blocks.append({
                'week_no': week_no,
                'date_from': w_start.isoformat(),
                'date_to': w_end.isoformat(),
                'period_label': period_label,
                'rows': [
                    {
                        'concept': _('Saldo inicial'),
                        'row_type': 'opening',
                        'amounts': cells_ini,
                        'total': total_ini,
                        'delta': delta_val,
                        'show_delta': True,
                    },
                    {
                        'concept': _('Remesa / entradas'),
                        'row_type': 'inflow',
                        'amounts': cells_deb,
                        'total': total_deb,
                        'delta': None,
                        'show_delta': False,
                    },
                    {
                        'concept': _('Salidas'),
                        'row_type': 'outflow',
                        'amounts': cells_cred,
                        'total': total_cred,
                        'delta': None,
                        'show_delta': False,
                    },
                ],
            })

        summary_lines = [
            {
                'label': _('Total entradas (débito) mes'),
                'amounts': [agg_debit[j.default_account_id.id] for j in journals],
                'total': sum(agg_debit.get(aid, 0.0) for aid in account_ids_set),
            },
            {
                'label': _('Total salidas (crédito) mes'),
                'amounts': [agg_credit[j.default_account_id.id] for j in journals],
                'total': sum(agg_credit.get(aid, 0.0) for aid in account_ids_set),
            },
        ]

        end_cells = []
        end_tot = 0.0
        for j in journals:
            aid = j.default_account_id.id
            v = end_bal.get(aid, 0.0)
            end_cells.append(v)
            end_tot += v
        summary_lines.append({
            'label': _('Saldo según libro al %(f)s')
            % {'f': month_end.strftime('%d/%m/%Y')},
            'amounts': end_cells,
            'total': end_tot,
        })

        compare_kpis = None
        if options.get('compare_previous') and not (wizard.date_from and wizard.date_to):
            prev_w = self._previous_period_wizard(wizard)
            prev_payload = self.build_payload(
                prev_w, options={'compare_previous': False, '_light': True},
            )
            compare_kpis = prev_payload.get('kpis') if prev_payload.get('has_data') else None

        kpis = self._build_kpis(
            journals, agg_debit, agg_credit, end_bal, account_ids_set, compare_kpis,
            company=company,
        )
        # v1 charts are pure presentation (no extra queries); skip them in light
        # mode where only KPIs/aggregations are consumed.
        charts = {} if options.get('_light') else self._build_charts(
            journals, week_blocks, agg_debit, agg_credit, end_bal,
        )

        period_title = '%s %s' % (month_name, wizard.year)
        if wizard.date_from and wizard.date_to:
            period_title = '%s — %s' % (
                wizard.date_from.strftime('%d/%m/%Y'),
                wizard.date_to.strftime('%d/%m/%Y'),
            )

        return {
            'has_data': True,
            'error_message': '',
            'journal_columns': journal_columns,
            'week_blocks': week_blocks,
            'summary_lines': summary_lines,
            'kpis': kpis,
            'charts': charts,
            'company_name': company.name or '',
            'month_year_title': period_title,
            'currency_symbol': symbol,
            'currency_id': currency.id,
            'subtitle': subtitle_txt,
            'month_end_str': month_end.strftime('%d/%m/%Y'),
            'generated_at': fields.Datetime.now().isoformat(),
            '_aggregations': aggregations,
        }
