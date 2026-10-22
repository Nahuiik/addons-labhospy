# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

"""Helpers to present statement reports in a currency other than company currency.

Uses ``res.currency._convert`` (same as Odoo core) so rates from
``gn_bank_rate`` / ``res.currency.rate`` apply automatically.
"""

from odoo import api, fields, models, _
from odoo.tools.misc import formatLang


class BiReportCurrencyHelper(models.AbstractModel):
    _name = 'bi.report.currency.helper'
    _description = 'Financial report currency conversion helper'

    @api.model
    def _convert_amt(self, amount, company, from_currency, to_currency, conv_date):
        if to_currency is None or from_currency == to_currency:
            return amount
        if amount is None:
            return 0.0
        d = fields.Date.to_date(conv_date) if conv_date else fields.Date.today()
        try:
            return from_currency._convert(float(amount), to_currency, company, d)
        except Exception:
            return float(amount)

    @api.model
    def _currency_dict(self, currency):
        return {
            'id': currency.id,
            'symbol': currency.symbol,
            'position': currency.position,
            'decimal_places': currency.decimal_places,
        }

    @api.model
    def _apply_statement_blocks(self, blocks, company, cc, target, conv_date):
        """Mutate dict of category -> {total, accounts: [{balance}]}."""
        if not blocks or not target or target == cc:
            return
        for _cat, block in blocks.items():
            if not isinstance(block, dict):
                continue
            block['total'] = self._convert_amt(
                block.get('total', 0.0), company, cc, target, conv_date)
            for acc in block.get('accounts') or []:
                if isinstance(acc, dict) and 'balance' in acc:
                    acc['balance'] = self._convert_amt(
                        acc['balance'], company, cc, target, conv_date)

    @api.model
    def _apply_bs_section_block(self, block, company, cc, target, conv_date):
        if not isinstance(block, dict) or not target or target == cc:
            return
        totals = block.get("total_by_period") or {}
        for pk, amount in list(totals.items()):
            totals[pk] = self._convert_amt(amount, company, cc, target, conv_date)
        block["total"] = totals.get("current", block.get("total", 0.0))
        for acc in block.get("accounts") or []:
            if not isinstance(acc, dict):
                continue
            balances = acc.get("balances") or {}
            for pk, amount in list(balances.items()):
                balances[pk] = self._convert_amt(amount, company, cc, target, conv_date)
            acc["balance"] = balances.get("current", acc.get("balance", 0.0))
            if acc.get("fx_balance") is not None:
                acc["fx_balance"] = self._convert_amt(acc["fx_balance"], company, cc, target, conv_date)

        def walk(nodes):
            for node in nodes or []:
                if not isinstance(node, dict):
                    continue
                nb = node.get("balances") or {}
                for pk, amount in list(nb.items()):
                    nb[pk] = self._convert_amt(amount, company, cc, target, conv_date)
                walk(node.get("children"))

        walk(block.get("hierarchy"))

    @api.model
    def apply_balance_sheet(self, result, report_currency_id):
        if not report_currency_id:
            return result
        company = self.env.company
        cc = company.currency_id
        target = self.env['res.currency'].browse(int(report_currency_id))
        if not target.exists() or target == cc:
            return result
        date_to = result.get('date_to')
        d = fields.Date.to_date(date_to) if date_to else fields.Date.today()

        for bucket in (result.get('assets') or {}, result.get('liabilities') or {}, result.get('equity') or {}):
            for block in bucket.values():
                self._apply_bs_section_block(block, company, cc, target, d)

        totals = result.get('totals') or {}
        by_period = totals.get('by_period') or {}
        for section_key, period_map in by_period.items():
            if isinstance(period_map, dict):
                for pk, amount in list(period_map.items()):
                    period_map[pk] = self._convert_amt(amount, company, cc, target, d)
        for k in ('assets', 'liabilities', 'equity', 'liabilities_equity'):
            if k in totals:
                totals[k] = self._convert_amt(totals[k], company, cc, target, d)

        cmp = result.get('comparison')
        if cmp:
            d2 = fields.Date.to_date(cmp.get('date_to')) if cmp.get('date_to') else d
            for bucket in (cmp.get('assets') or {}, cmp.get('liabilities') or {}, cmp.get('equity') or {}):
                for block in bucket.values():
                    if isinstance(block, dict) and 'total' in block:
                        block['total'] = self._convert_amt(block.get('total', 0.0), company, cc, target, d2)
            ct = cmp.get('totals') or {}
            for k in list(ct.keys()):
                ct[k] = self._convert_amt(ct[k], company, cc, target, d2)

        result['currency_data'] = self._currency_dict(target)
        result['report_currency_note'] = _(
            'Amounts converted to %(cur)s using the rate at %(date)s.',
            cur=target.name,
            date=fields.Date.to_string(d),
        )
        return result

    @api.model
    def _apply_pl_section_block(self, block, company, cc, target, conv_date):
        if not isinstance(block, dict) or not target or target == cc:
            return
        totals = block.get("total_by_period") or {}
        for pk, amount in list(totals.items()):
            totals[pk] = self._convert_amt(amount, company, cc, target, conv_date)
        block["total"] = totals.get("current", block.get("total", 0.0))
        for acc in block.get("accounts") or []:
            if not isinstance(acc, dict):
                continue
            balances = acc.get("balances") or {}
            for pk, amount in list(balances.items()):
                balances[pk] = self._convert_amt(amount, company, cc, target, conv_date)
            acc["balance"] = balances.get("current", acc.get("balance", 0.0))

        def walk(nodes):
            for node in nodes or []:
                if not isinstance(node, dict):
                    continue
                nb = node.get("balances") or {}
                for pk, amount in list(nb.items()):
                    nb[pk] = self._convert_amt(amount, company, cc, target, conv_date)
                walk(node.get("children"))

        walk(block.get("hierarchy"))

    @api.model
    def apply_profit_loss(self, result, report_currency_id):
        if not report_currency_id:
            return result
        company = self.env.company
        cc = company.currency_id
        target = self.env['res.currency'].browse(int(report_currency_id))
        if not target.exists() or target == cc:
            return result
        date_to = result.get('date_to')
        d = fields.Date.to_date(date_to) if date_to else fields.Date.today()

        for bucket in (result.get('income') or {}, result.get('expense') or {}):
            for block in bucket.values():
                self._apply_pl_section_block(block, company, cc, target, d)

        for period in result.get('periods') or []:
            if period.get('is_current'):
                continue
            d2 = fields.Date.to_date(period.get('date_to')) if period.get('date_to') else d
            # Period labels stay; amounts already converted per block above using current conv date.
            # Re-convert comparison-only keys with their period end date for accuracy.
            for bucket in (result.get('income') or {}, result.get('expense') or {}):
                for block in bucket.values():
                    if not isinstance(block, dict):
                        continue
                    pk = period.get('key')
                    totals = block.get('total_by_period') or {}
                    if pk in totals:
                        totals[pk] = self._convert_amt(
                            totals[pk], company, cc, target, d2)
                    for acc in block.get('accounts') or []:
                        balances = acc.get('balances') or {}
                        if pk in balances:
                            balances[pk] = self._convert_amt(
                                balances[pk], company, cc, target, d2)

        cmp = result.get('comparison')
        if cmp:
            d2 = fields.Date.to_date(cmp.get('date_to')) if cmp.get('date_to') else d
            for bucket in (cmp.get('income') or {}, cmp.get('expense') or {}):
                for block in bucket.values():
                    if isinstance(block, dict) and 'total' in block:
                        block['total'] = self._convert_amt(block.get('total', 0.0), company, cc, target, d2)
                    for acc in (block.get('accounts') or [] if isinstance(block, dict) else []):
                        if isinstance(acc, dict) and 'balance' in acc:
                            acc['balance'] = self._convert_amt(acc['balance'], company, cc, target, d2)

        result['currency_data'] = self._currency_dict(target)
        result['report_currency_note'] = _(
            'Amounts converted to %(cur)s using the rate at %(date)s.',
            cur=target.name,
            date=fields.Date.to_string(d),
        )
        return result

    @api.model
    def apply_cash_flow(self, result, report_currency_id):
        if not report_currency_id:
            return result
        company = self.env.company
        cc = company.currency_id
        target = self.env['res.currency'].browse(int(report_currency_id))
        if not target.exists() or target == cc:
            return result
        date_to = result.get('date_to')
        d = fields.Date.to_date(date_to) if date_to else fields.Date.today()

        def convert_cash_block(block, conv_date):
            dloc = fields.Date.to_date(conv_date) if conv_date else d

            def cnv2(x):
                return self._convert_amt(x, company, cc, target, dloc)

            for key in ('opening_balance', 'closing_balance', 'net_increase', 'unexplained_difference'):
                if key in block:
                    block[key] = cnv2(block[key])
            for lst_key in ('opening_accounts', 'closing_accounts'):
                for acc in block.get(lst_key) or []:
                    if isinstance(acc, dict) and 'balance' in acc:
                        acc['balance'] = cnv2(acc['balance'])
            secs = block.get('sections') or {}
            for sec in secs.values():
                if not isinstance(sec, dict):
                    continue
                sec['total'] = cnv2(sec.get('total', 0.0))
                for sub in (sec.get('subsections') or {}).values():
                    if not isinstance(sub, dict):
                        continue
                    sub['total'] = cnv2(sub.get('total', 0.0))
                    for acc in sub.get('accounts') or []:
                        if isinstance(acc, dict) and 'balance' in acc:
                            acc['balance'] = cnv2(acc['balance'])

        convert_cash_block(result, date_to)
        cmp_cf = result.get('comparison')
        if isinstance(cmp_cf, dict):
            convert_cash_block(cmp_cf, cmp_cf.get('date_to'))
        result['currency_data'] = self._currency_dict(target)
        result['report_currency_note'] = _(
            'Amounts converted to %(cur)s using the rate at %(date)s.',
            cur=target.name,
            date=fields.Date.to_string(d),
        )
        return result

    @api.model
    def apply_tax_report(self, result, report_currency_id):
        if not report_currency_id:
            return result
        company = self.env.company
        cc = company.currency_id
        target = self.env['res.currency'].browse(int(report_currency_id))
        if not target.exists() or target == cc:
            return result
        date_to = result.get('date_to')
        d = fields.Date.to_date(date_to) if date_to else fields.Date.today()
        col_dates = {
            c.get('key'): fields.Date.to_date(c['date_to']) if c.get('date_to') else d
            for c in (result.get('columns') or [])
        }

        for col in result.get('columns') or []:
            ck = col.get('key')
            dcol = col_dates.get(ck, d)

            def cnv_col(x):
                return self._convert_amt(x, company, cc, target, dcol)

            for _sec_key, sec in (result.get('sections') or {}).items():
                if not isinstance(sec, dict):
                    continue
                totals = sec.get('totals') or {}
                bucket = totals.get(ck)
                if isinstance(bucket, dict):
                    for fld in ('base', 'tax'):
                        if fld in bucket:
                            bucket[fld] = cnv_col(bucket[fld])
                for tax in sec.get('taxes') or []:
                    amts = tax.get('amounts') or {}
                    cell = amts.get(ck)
                    if isinstance(cell, dict):
                        for field in ('base', 'tax'):
                            if field in cell:
                                cell[field] = cnv_col(cell[field])

        decl = result.get('declaration_totals') or {}
        for col_key, bucket in decl.items():
            dcol = col_dates.get(col_key, d)
            for fld in ('sales_tax', 'purchase_tax', 'net_tax_due'):
                if fld in bucket:
                    bucket[fld] = self._convert_amt(
                        bucket[fld], company, cc, target, dcol)

        t = result.get('totals') or {}
        for fld in ('sales_tax', 'sales_base', 'purchase_tax', 'purchase_base', 'net_tax_due'):
            if fld in t:
                t[fld] = self._convert_amt(t[fld], company, cc, target, d)
        result['currency_data'] = self._currency_dict(target)
        result['report_currency_note'] = _(
            'Amounts converted to %(cur)s using the rate at %(date)s.',
            cur=target.name,
            date=fields.Date.to_string(d),
        )
        return result

    @api.model
    def apply_executive_summary(self, result, report_currency_id):
        if not report_currency_id:
            return result
        company = self.env.company
        cc = company.currency_id
        target = self.env['res.currency'].browse(int(report_currency_id))
        if not target.exists() or target == cc:
            return result
        date_to = result.get('date_to')
        d = fields.Date.to_date(date_to) if date_to else fields.Date.today()

        def cnv_main(x):
            return self._convert_amt(x, company, cc, target, d)

        def fmt(v):
            return formatLang(self.env, v, currency_obj=target)

        for row in result.get('rows') or []:
            if row.get('is_pct'):
                continue
            if 'value' in row:
                v = cnv_main(row['value'])
                row['value'] = v
                row['formatted'] = fmt(v)

        cmp = result.get('comparison')
        if cmp:
            d_cmp = fields.Date.to_date(cmp.get('date_to')) if cmp.get('date_to') else d

            def cnv_cmp(x):
                return self._convert_amt(x, company, cc, target, d_cmp)

            comp_by_key = {r['key']: r for r in cmp.get('rows', [])}
            for row in result.get('rows') or []:
                k = row.get('key')
                if row.get('is_pct') or k not in comp_by_key:
                    continue
                cr = comp_by_key[k]
                cv = cnv_cmp(cr['value'])
                row['comparison_value'] = cv
                row['comparison_formatted'] = fmt(cv)

        result['currency_data'] = self._currency_dict(target)
        result['report_currency_note'] = _(
            'Amounts converted to %(cur)s using the rate at %(date)s.',
            cur=target.name,
            date=fields.Date.to_string(d),
        )
        return result

    @api.model
    def apply_trial_balance(self, account_data, balance_dict, report_currency_id, date_to):
        if not report_currency_id:
            return account_data, balance_dict
        company = self.env.company
        cc = company.currency_id
        target = self.env['res.currency'].browse(int(report_currency_id))
        if not target.exists() or target == cc:
            return account_data, balance_dict
        d = fields.Date.to_date(date_to) if date_to else fields.Date.today()

        def cnv(x):
            return self._convert_amt(x, company, cc, target, d)

        def fmt(a):
            return formatLang(self.env, a, currency_obj=target, grouping=True)

        for row in account_data:
            id_raw = cnv(row.get('initial_debit_raw', 0.0))
            ic_raw = cnv(row.get('initial_credit_raw', 0.0))
            pd_raw = cnv(row.get('period_debit_raw', 0.0))
            pc_raw = cnv(row.get('period_credit_raw', 0.0))
            ed_raw = cnv(row.get('ending_debit_raw', 0.0))
            ec_raw = cnv(row.get('ending_credit_raw', 0.0))
            bi = id_raw - ic_raw
            bf = ed_raw - ec_raw
            row['initial_debit'] = fmt(id_raw)
            row['initial_credit'] = fmt(ic_raw)
            row['period_debit'] = fmt(pd_raw)
            row['period_credit'] = fmt(pc_raw)
            row['ending_debit'] = fmt(ed_raw)
            row['ending_credit'] = fmt(ec_raw)
            row['balance_inicial'] = fmt(bi)
            row['balance_inicial_negative'] = bi < 0
            row['balance_final'] = fmt(bf)
            row['balance_final_negative'] = bf < 0
            row['balance_inicial_raw'] = bi
            row['balance_final_raw'] = bf
            row['period_debit_raw'] = pd_raw
            row['period_credit_raw'] = pc_raw
            row['initial_debit_raw'] = id_raw
            row['initial_credit_raw'] = ic_raw
            row['ending_debit_raw'] = ed_raw
            row['ending_credit_raw'] = ec_raw

        # Recompute totals
        tid = tic = tpd = tpc = ted = tec = 0.0
        for row in account_data:
            tid += row.get('initial_debit_raw', 0.0)
            tic += row.get('initial_credit_raw', 0.0)
            tpd += row.get('period_debit_raw', 0.0)
            tpc += row.get('period_credit_raw', 0.0)
            ted += row.get('ending_debit_raw', 0.0)
            tec += row.get('ending_credit_raw', 0.0)
        tbi = tid - tic
        tbf = ted - tec
        balance_dict['total_initial_debit'] = fmt(tid)
        balance_dict['total_initial_credit'] = fmt(tic)
        balance_dict['total_period_debit'] = fmt(tpd)
        balance_dict['total_period_credit'] = fmt(tpc)
        balance_dict['total_ending_debit'] = fmt(ted)
        balance_dict['total_ending_credit'] = fmt(tec)
        balance_dict['total_balance_inicial'] = fmt(tbi)
        balance_dict['total_balance_inicial_negative'] = tbi < 0
        balance_dict['total_balance_final'] = fmt(tbf)
        balance_dict['total_balance_final_negative'] = tbf < 0
        balance_dict['currency'] = self._currency_dict(target)
        balance_dict['report_currency_note'] = _(
            'Amounts converted to %(cur)s using the rate at %(date)s.',
            cur=target.name,
            date=fields.Date.to_string(d),
        )

        def rebuild_hierarchy(nodes):
            for node in nodes or []:
                if not isinstance(node, dict):
                    continue
                if node.get('type') == 'account':
                    aid = node.get('id')
                    accrow = next((r for r in account_data if r['id'] == aid), None)
                    if accrow:
                        node['balance_inicial'] = accrow['balance_inicial']
                        node['balance_inicial_negative'] = accrow['balance_inicial_negative']
                        node['balance_final'] = accrow['balance_final']
                        node['balance_final_negative'] = accrow['balance_final_negative']
                        node['period_debit'] = accrow['period_debit']
                        node['period_credit'] = accrow['period_credit']
                else:
                    bi_raw = node.get('total_balance_inicial_raw', 0.0)
                    bf_raw = node.get('total_balance_final_raw', 0.0)
                    pd_raw = node.get('total_period_debit_raw', 0.0)
                    pc_raw = node.get('total_period_credit_raw', 0.0)
                    node['total_balance_inicial_raw'] = cnv(bi_raw)
                    node['total_balance_final_raw'] = cnv(bf_raw)
                    node['total_period_debit_raw'] = cnv(pd_raw)
                    node['total_period_credit_raw'] = cnv(pc_raw)
                    node['total_balance_inicial'] = fmt(node['total_balance_inicial_raw'])
                    node['total_balance_final'] = fmt(node['total_balance_final_raw'])
                    node['total_period_debit'] = fmt(node['total_period_debit_raw'])
                    node['total_period_credit'] = fmt(node['total_period_credit_raw'])
                    node['total_balance_inicial_negative'] = node['total_balance_inicial_raw'] < 0
                    node['total_balance_final_negative'] = node['total_balance_final_raw'] < 0
                    rebuild_hierarchy(node.get('children'))

        rebuild_hierarchy(balance_dict.get('hierarchy'))
        return account_data, balance_dict
