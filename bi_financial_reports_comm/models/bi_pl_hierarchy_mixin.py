# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

"""Clean-room helpers for P&L section hierarchy and multi-period balances."""

from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.tools.date_utils import get_fiscal_year, get_month, get_quarter


class BiPlHierarchyMixin(models.AbstractModel):
    _name = "bi.pl.hierarchy.mixin"
    _description = "Profit and Loss hierarchy and comparison helpers"

    @api.model
    def _pl_format_period_label(self, date_from, date_to, date_filter_type):
        df = fields.Date.from_string(date_from) if isinstance(date_from, str) else date_from
        dt = fields.Date.from_string(date_to) if isinstance(date_to, str) else date_to
        if not df or not dt:
            return ""
        if date_filter_type == "year":
            return str(dt.year)
        if date_filter_type == "quarter":
            quarter = (dt.month - 1) // 3 + 1
            return f"Q{quarter} {dt.year}"
        if date_filter_type == "month":
            return dt.strftime("%b %Y")
        return df.strftime("%d/%m/%Y") + " - " + dt.strftime("%d/%m/%Y")

    @api.model
    def _pl_shift_comparison_period(self, date_from, date_to, comparison_filter, offset, date_filter_type):
        df = fields.Date.from_string(date_from) if isinstance(date_from, str) else date_from
        dt = fields.Date.from_string(date_to) if isinstance(date_to, str) else date_to
        if comparison_filter == "previous_period":
            pt = date_filter_type or "month"
            if pt == "month":
                cmp_to = dt - relativedelta(months=offset)
                cmp_from, cmp_to = get_month(cmp_to)
            elif pt == "quarter":
                cmp_to = dt - relativedelta(months=3 * offset)
                cmp_from, cmp_to = get_quarter(cmp_to)
            else:
                cmp_to = dt - relativedelta(years=offset)
                cmp_from, cmp_to = get_fiscal_year(cmp_to)
        elif comparison_filter == "same_last_year":
            cmp_from = df - relativedelta(years=offset)
            cmp_to = dt - relativedelta(years=offset)
        elif comparison_filter == "specific_date":
            cmp_date_to = self.env.context.get("comparison_date_to")
            if not cmp_date_to:
                return None
            cmp_to = fields.Date.from_string(cmp_date_to)
            pt = date_filter_type or "month"
            if pt == "month":
                cmp_from, cmp_to = get_month(cmp_to)
            elif pt == "quarter":
                cmp_from, cmp_to = get_quarter(cmp_to)
            else:
                cmp_from, cmp_to = get_fiscal_year(cmp_to)
        else:
            return None
        return {
            "date_from": cmp_from.strftime("%Y-%m-%d"),
            "date_to": cmp_to.strftime("%Y-%m-%d"),
            "string": self._pl_format_period_label(cmp_from, cmp_to, date_filter_type),
        }

    @api.model
    def _pl_get_report_periods(self, date_from, date_to, context=None):
        context = context or self.env.context
        date_filter_type = context.get("date_filter_type", "month")
        comparison_filter = context.get("comparison_filter", "no_comparison")
        number_period = int(context.get("comparison_number_period") or 1)
        period_order = context.get("comparison_period_order", "descending")

        current = {
            "key": "current",
            "date_from": date_from,
            "date_to": date_to,
            "label": self._pl_format_period_label(date_from, date_to, date_filter_type),
            "is_current": True,
        }
        if comparison_filter in ("no_comparison", None, ""):
            return [current]

        comparisons = []
        if comparison_filter == "specific_date":
            cmp = self._pl_shift_comparison_period(
                date_from, date_to, comparison_filter, 1, date_filter_type
            )
            if cmp:
                comparisons.append({
                    "key": "cmp_1",
                    "date_from": cmp["date_from"],
                    "date_to": cmp["date_to"],
                    "label": cmp["string"],
                    "is_current": False,
                })
        else:
            for i in range(1, max(1, number_period) + 1):
                cmp = self._pl_shift_comparison_period(
                    date_from, date_to, comparison_filter, i, date_filter_type
                )
                if cmp:
                    comparisons.append({
                        "key": f"cmp_{i}",
                        "date_from": cmp["date_from"],
                        "date_to": cmp["date_to"],
                        "label": cmp["string"],
                        "is_current": False,
                    })

        if period_order == "ascending":
            return comparisons + [current]
        return [current] + comparisons

    # ------------------------------------------------------------------
    # Analytic columns (clean-room): each selected analytic account becomes
    # a column; a final "Total" column holds the full (unfiltered) balance.
    # ------------------------------------------------------------------
    @api.model
    def _an_columns_enabled(self):
        """True when the report must render analytic accounts as columns."""
        ctx = self.env.context
        return bool(ctx.get("analytic_columns")) and bool(ctx.get("analytic_account_ids"))

    @api.model
    def _an_build_columns(self):
        """Ordered column descriptors: one per selected analytic account + Total."""
        ctx = self.env.context
        ids = [aid for aid in (ctx.get("analytic_account_ids") or []) if aid]
        accounts = self.env["account.analytic.account"].browse(ids).exists()
        columns = [
            {"key": "an_%d" % acc.id, "label": acc.name or _("(unnamed)"), "analytic_id": acc.id}
            for acc in accounts
        ]
        columns.append({"key": "total", "label": _("Total"), "analytic_id": None})
        return columns

    @api.model
    def _an_primary_key(self):
        """Key of the column holding the report's headline figure."""
        return "total" if self._an_columns_enabled() else "current"

    @api.model
    def _an_analytic_balance_map(self, accounts, analytic_ids, date_from, date_to, flip_income=True):
        """Return {analytic_id: {account_id: gl_balance}} prorated from analytic lines.

        ``account.analytic.line.amount`` already stores the prorated share with the
        opposite sign of the journal item balance, so the GL contribution is ``-amount``.
        """
        if not accounts or not analytic_ids:
            return {}
        ctx = self.env.context
        domain = [
            ("general_account_id", "in", accounts.ids),
            ("account_id", "in", list(analytic_ids)),
        ]
        if date_from:
            domain.append(("date", ">=", date_from))
        if date_to:
            domain.append(("date", "<=", date_to))
        if ctx.get("target_move", "all") == "posted":
            domain.append(("move_line_id.parent_state", "=", "posted"))
        journal_ids = ctx.get("journal_ids")
        if journal_ids:
            domain.append(("move_line_id.journal_id", "in", journal_ids))
        grouped = self.env["account.analytic.line"]._read_group(
            domain,
            groupby=["account_id", "general_account_id"],
            aggregates=["amount:sum"],
        )
        income_types = ("income", "income_other")
        acc_types = {acc.id: acc.account_type for acc in accounts}
        result = defaultdict(dict)
        for analytic, gen_account, amount_sum in grouped:
            gl_balance = -(amount_sum or 0.0)
            if flip_income and acc_types.get(gen_account.id) in income_types:
                gl_balance = -gl_balance
            result[analytic.id][gen_account.id] = gl_balance
        return result

    @api.model
    def _an_full_balance_map(self, accounts, date_from, date_to, flip_income=True):
        """Return {account_id: balance} for the Total column (no analytic filter)."""
        if not accounts:
            return {}
        ctx = self.env.context
        domain = [("account_id", "in", accounts.ids), *self._pl_aml_layout_domain()]
        if ctx.get("target_move", "all") == "posted":
            domain.append(("parent_state", "=", "posted"))
        if date_from:
            domain.append(("date", ">=", date_from))
        if date_to:
            domain.append(("date", "<=", date_to))
        journal_ids = ctx.get("journal_ids")
        if journal_ids:
            domain.append(("journal_id", "in", journal_ids))
        grouped = self.env["account.move.line"]._read_group(
            domain, groupby=["account_id"], aggregates=["balance:sum"]
        )
        income_types = ("income", "income_other")
        acc_types = {acc.id: acc.account_type for acc in accounts}
        result = {}
        for account, balance in grouped:
            value = balance or 0.0
            if flip_income and acc_types.get(account.id) in income_types:
                value = -value
            result[account.id] = value
        return result

    @api.model
    def _an_column_balances_map(self, accounts, columns, date_from, date_to, display_account="movement", flip_income=True):
        """Return {column_key: {account_id: balance}} for analytic columns."""
        analytic_ids = [c["analytic_id"] for c in columns if c.get("analytic_id")]
        by_analytic = self._an_analytic_balance_map(
            accounts, analytic_ids, date_from, date_to, flip_income=flip_income
        )
        full_map = None
        result = {}
        for col in columns:
            if col.get("analytic_id"):
                balmap = dict(by_analytic.get(col["analytic_id"], {}))
            else:
                if full_map is None:
                    full_map = self._an_full_balance_map(
                        accounts, date_from, date_to, flip_income=flip_income
                    )
                balmap = dict(full_map)
            if display_account in ("movement", "not_zero"):
                balmap = {aid: val for aid, val in balmap.items() if val}
            result[col["key"]] = balmap
        return result

    @api.model
    def action_open_analytic_cell(self, options, account_id, analytic_id):
        """Drill-down for an analytic-column cell.

        With an analytic account it opens the prorated ``account.analytic.line``
        records that build the cell; the Total column falls back to journal items.
        """
        opts = dict(options or {})
        if not analytic_id:
            return self.action_open_aml(opts, account_id)
        helper = self.env["bi.report.drilldown.helper"]
        date_from, date_to = helper.resolve_drilldown_dates(opts)
        if opts.get("_an_cumulative"):
            date_from = None
        domain = [
            ("general_account_id", "=", int(account_id)),
            ("account_id", "=", int(analytic_id)),
        ]
        if date_from:
            domain.append(("date", ">=", date_from))
        if date_to:
            domain.append(("date", "<=", date_to))
        if (opts.get("target_move") or "all") == "posted":
            domain.append(("move_line_id.parent_state", "=", "posted"))
        journal_ids = opts.get("journal_ids") or []
        if journal_ids:
            domain.append(("move_line_id.journal_id", "in", journal_ids))
        account = self.env["account.account"].browse(int(account_id))
        analytic = self.env["account.analytic.account"].browse(int(analytic_id))
        name = _(
            "Apuntes analíticos: %(acc)s / %(an)s",
            acc=account.code or account.name or "",
            an=analytic.name or "",
        )
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": "account.analytic.line",
            "views": [(False, "list"), (False, "form")],
            "view_mode": "list",
            "domain": domain,
            "target": "current",
        }

    @api.model
    def _an_matrix_xlsx(self, data, sheet_name):
        """Render an analytic-columns matrix (``data['analytic_matrix']``) to XLSX.

        Shared by the P&L, Balance Sheet and Trial Balance ``*_owl_xlsx`` methods
        so the analytic layout exports the very same columns shown on screen.
        """
        import io
        import base64
        import xlsxwriter

        matrix = (data or {}).get("analytic_matrix") or {}
        columns = matrix.get("columns") or []
        rows = matrix.get("rows") or []

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet((sheet_name or "Report")[:31])

        title_fmt = workbook.add_format({"bold": True, "font_size": 13})
        sub_fmt = workbook.add_format({"font_size": 9, "italic": True})
        head_fmt = workbook.add_format(
            {"bold": True, "align": "center", "valign": "vcenter",
             "bg_color": "#D9D9D9", "border": 1}
        )
        label_fmt = workbook.add_format({"border": 1})
        label_bold = workbook.add_format({"bold": True, "border": 1, "bg_color": "#F2F2F2"})
        money_fmt = workbook.add_format({"num_format": "#,##0.00", "border": 1})
        money_bold = workbook.add_format(
            {"num_format": "#,##0.00", "bold": True, "border": 1, "bg_color": "#F2F2F2"}
        )

        sheet.set_column(0, 0, 45)
        sheet.set_column(1, max(len(columns), 1), 18)

        row = 0
        sheet.write(row, 0, sheet_name or "", title_fmt)
        row += 1
        period = "%s - %s" % (data.get("date_from") or "", data.get("date_to") or "")
        sheet.write(row, 0, period.strip(" -"), sub_fmt)
        row += 2

        sheet.write(row, 0, _("Cuenta"), head_fmt)
        for ci, col in enumerate(columns):
            sheet.write(row, ci + 1, col.get("label") or "", head_fmt)
        row += 1

        bold_types = {"section", "subtotal", "main_header", "main_total"}
        for line in rows:
            is_bold = line.get("type") in bold_types
            indent = "    " if line.get("type") == "account" else ""
            sheet.write(
                row, 0, indent + (line.get("label") or ""),
                label_bold if is_bold else label_fmt,
            )
            values = line.get("values") or {}
            for ci, col in enumerate(columns):
                amount = float(values.get(col.get("key")) or 0.0)
                sheet.write_number(
                    row, ci + 1, amount, money_bold if is_bold else money_fmt
                )
            row += 1

        workbook.close()
        output.seek(0)
        file_name = (sheet_name or "Report").strip().replace(" ", "_") + ".xlsx"
        return {
            "excel_file": base64.b64encode(output.read()).decode("utf-8"),
            "file_name": file_name,
        }

    @api.model
    def _pl_aml_layout_domain(self):
        helper = self.env["bi.report.drilldown.helper"]
        return helper.aml_display_type_domain()

    @api.model
    def _pl_analytic_domain(self):
        ctx = self.env.context
        analytic_ids = ctx.get("analytic_account_ids") or []
        if not analytic_ids:
            return []
        domain = [("analytic_distribution", "in", analytic_ids)]
        if ctx.get("include_analytic_without_aml"):
            return ["|", ("analytic_distribution", "in", analytic_ids), ("analytic_distribution", "=", False)]
        return domain

    @api.model
    def _pl_account_balance(self, account, date_from, date_to):
        target_move = self.env.context.get("target_move", "all")
        journal_ids = self.env.context.get("journal_ids")
        if self.env.context.get("report_cash_basis"):
            return self.env["bi.cash.basis.helper"].account_balance(
                account, date_from, date_to, target_move=target_move, journal_ids=journal_ids
            )
        domain = [("account_id", "=", account.id), *self._pl_aml_layout_domain(), *self._pl_analytic_domain()]
        if target_move == "posted":
            domain.append(("parent_state", "=", "posted"))
        if date_from:
            domain.append(("date", ">=", date_from))
        if date_to:
            domain.append(("date", "<=", date_to))
        if journal_ids:
            domain.append(("journal_id", "in", journal_ids))
        grouped = self.env["account.move.line"]._read_group(
            domain, groupby=["account_id"], aggregates=["balance:sum"]
        )
        balance = grouped[0][1] if grouped else 0.0
        if account.account_type in ("income", "income_other"):
            return -balance
        return balance

    @api.model
    def _pl_balances_for_period(self, accounts, date_from, date_to, display_account="movement"):
        balances = {}
        for account in accounts:
            bal = self._pl_account_balance(account, date_from, date_to)
            if display_account == "not_zero" and not bal:
                continue
            if display_account == "movement" and not bal:
                continue
            if display_account == "all" or bal:
                balances[account.id] = bal
        return balances

    @api.model
    def _pl_period_balances_map(self, accounts, periods, display_account="movement", balance_as_of=False):
        result = {}
        for period in periods:
            date_from = None if balance_as_of else period["date_from"]
            date_to = period["date_to"]
            result[period["key"]] = self._pl_balances_for_period(
                accounts, date_from, date_to, display_account
            )
        return result

    @api.model
    def _pl_sum_balances(self, period_balances, period_keys):
        return {pk: sum(period_balances.get(pk, {}).values()) for pk in period_keys}

    @api.model
    def _pl_accounts_payload(self, accounts, period_balances, period_keys):
        account_ids = set()
        for pb in period_balances.values():
            account_ids.update(pb.keys())
        rows = []
        for account in accounts.filtered(lambda a: a.id in account_ids):
            balances = {
                pk: period_balances.get(pk, {}).get(account.id, 0.0) for pk in period_keys
            }
            rows.append({
                "id": account.id,
                "code": account.code,
                "name": account.name,
                "group_id": account.group_id.id if account.group_id else None,
                "balances": balances,
                "balance": balances.get(self._an_primary_key(), balances.get("current", 0.0)),
            })
        rows.sort(key=lambda r: r.get("code") or "")
        return rows

    @api.model
    def _pl_aggregate_children_balances(self, children, period_keys):
        totals = {pk: 0.0 for pk in period_keys}
        for child in children:
            child_bal = child.get("balances") or {}
            for pk in period_keys:
                totals[pk] += float(child_bal.get(pk, 0.0) or 0.0)
        return totals

    @api.model
    def _pl_hierarchy_too_flat(self, hierarchy):
        for node in hierarchy or []:
            if node.get("type") != "group":
                continue
            acc_count = sum(1 for c in (node.get("children") or []) if c.get("type") == "account")
            group_count = sum(1 for c in (node.get("children") or []) if c.get("type") == "group")
            if acc_count >= 3 and group_count > 0:
                return True
        return False

    @api.model
    def _pl_group_has_section_accounts(self, group, accounts, groups):
        if accounts.filtered(lambda a: a.group_id.id == group.id):
            return True
        for child in groups.filtered(lambda g: g.parent_id and g.parent_id.id == group.id):
            if self._pl_group_has_section_accounts(child, accounts, groups):
                return True
        return False

    @api.model
    def _pl_build_group_hierarchy(self, accounts, period_balances, period_keys):
        AccountGroup = self.env["account.group"].with_user(SUPERUSER_ID)
        company = self.env.company
        company_ids = [company.id]
        if hasattr(company, "root_id") and company.root_id and company.root_id.id != company.id:
            company_ids.append(company.root_id.id)

        groups = AccountGroup.search([("company_id", "in", company_ids)], order="code_prefix_start")
        if not groups:
            return []

        account_ids = set(accounts.ids)
        direct_account_ids = defaultdict(list)
        for account in accounts:
            gid = account.group_id.id if account.group_id else None
            if gid and account.id in account_ids:
                direct_account_ids[gid].append(account.id)

        def account_node(acc_id, level):
            account = accounts.browse(acc_id)
            balances = {
                pk: period_balances.get(pk, {}).get(acc_id, 0.0) for pk in period_keys
            }
            return {
                "type": "account",
                "key": f"acc_{acc_id}",
                "id": acc_id,
                "code": account.code,
                "name": account.name,
                "level": level,
                "children": [],
                "balances": balances,
            }

        def build_node(group, level):
            gid = group.id
            children = []
            for child_group in groups.filtered(lambda g: g.parent_id and g.parent_id.id == gid).sorted(
                key=lambda g: (len(g.code_prefix_start or ""), g.code_prefix_start or "")
            ):
                child_node = build_node(child_group, level + 1)
                if child_node:
                    children.append(child_node)
            for acc_id in sorted(direct_account_ids.get(gid, [])):
                children.append(account_node(acc_id, level + 1))
            if not children:
                return None
            balances = self._pl_aggregate_children_balances(children, period_keys)
            code = group.code_prefix_start or ""
            name = group.name or ""
            return {
                "type": "group",
                "id": gid,
                "key": f"ag_{gid}",
                "code": code,
                "name": name,
                "label": f"{code} {name}".strip() if code else name,
                "level": level,
                "children": children,
                "balances": balances,
            }

        roots = groups.filtered(lambda g: not g.parent_id).sorted(
            key=lambda g: (len(g.code_prefix_start or ""), g.code_prefix_start or "")
        )
        hierarchy = []
        for root in roots:
            if not self._pl_group_has_section_accounts(root, accounts, groups):
                continue
            node = build_node(root, 0)
            if node:
                hierarchy.append(node)

        ungrouped = accounts.filtered(lambda a: not a.group_id and a.id in account_ids)
        if ungrouped:
            children = [account_node(a.id, 1) for a in ungrouped.sorted(key=lambda x: x.code)]
            hierarchy.append({
                "type": "group",
                "id": None,
                "key": "ungrouped",
                "code": "",
                "name": _("Sin grupo"),
                "label": _("Sin grupo"),
                "level": 0,
                "children": children,
                "balances": self._pl_aggregate_children_balances(children, period_keys),
            })
        return hierarchy

    @api.model
    def _pl_code_base(self, code):
        if not code:
            return ""
        return str(code).split(".")[0].rstrip("0") or str(code).split(".")[0]

    @api.model
    def _pl_prefix_path(self, code):
        base = self._pl_code_base(code)
        if not base:
            return []
        digits = "".join(c for c in base if c.isdigit())
        if not digits:
            return [base]
        breakpoints = [1, 2, 4, 6, 8]
        path = []
        for bp in breakpoints:
            if bp <= len(digits):
                prefix = digits[:bp]
                if not path or path[-1] != prefix:
                    path.append(prefix)
        if not path or path[-1] != digits:
            path.append(digits)
        return path

    @api.model
    def _pl_build_code_prefix_hierarchy(self, accounts, period_balances, period_keys):
        account_ids = set(accounts.ids)
        tree = {}
        prefix_to_accounts = defaultdict(list)
        AccountGroup = self.env["account.group"].with_user(SUPERUSER_ID)
        company_ids = [self.env.company.id]
        if hasattr(self.env.company, "root_id") and self.env.company.root_id:
            company_ids.append(self.env.company.root_id.id)
        groups = AccountGroup.search([("company_id", "in", company_ids)], order="code_prefix_start")
        group_by_prefix = {g.code_prefix_start: g for g in groups}

        for account in accounts:
            if account.id not in account_ids:
                continue
            path = self._pl_prefix_path(account.code)
            if len(path) < 2:
                prefix_to_accounts[path[0] if path else "other"].append(account.id)
                continue
            leaf_prefix = path[-1]
            prefix_to_accounts[leaf_prefix].append(account.id)
            for prefix in path:
                tree[prefix] = tree.get(prefix, {
                    "prefix": prefix,
                    "parent": path[path.index(prefix) - 1] if path.index(prefix) > 0 else None,
                })

        def account_node(acc_id, level):
            account = accounts.browse(acc_id)
            balances = {
                pk: period_balances.get(pk, {}).get(acc_id, 0.0) for pk in period_keys
            }
            return {
                "type": "account",
                "key": f"acc_{acc_id}",
                "id": acc_id,
                "code": account.code,
                "name": account.name,
                "level": level,
                "children": [],
                "balances": balances,
            }

        def make_node(prefix, level):
            acc_ids = prefix_to_accounts.get(prefix, [])
            group = group_by_prefix.get(prefix)
            name = group.name if group else _("Cuentas %s") % prefix
            children = []
            for child_prefix, data in tree.items():
                if data.get("parent") == prefix:
                    child = make_node(child_prefix, level + 1)
                    if child:
                        children.append(child)
            for acc_id in sorted(acc_ids):
                children.append(account_node(acc_id, level + 1))
            if not children:
                return None
            children.sort(key=lambda c: (c.get("type") != "group", c.get("code", "")))
            return {
                "type": "group",
                "id": group.id if group else None,
                "key": f"cp_{prefix}",
                "code": prefix,
                "name": name,
                "label": f"{prefix} {name}".strip(),
                "level": level,
                "children": children,
                "balances": self._pl_aggregate_children_balances(children, period_keys),
            }

        result = []
        for root_prefix in sorted(
            [p for p, data in tree.items() if data.get("parent") is None],
            key=lambda x: (len(x), x),
        ):
            node = make_node(root_prefix, 0)
            if node:
                result.append(node)
        return result

    @api.model
    def _pl_build_section_payload(self, accounts, periods, use_hierarchy=False, balance_as_of=False, flip_income=True):
        display_account = self.env.context.get("display_account", "movement")
        if self._an_columns_enabled():
            columns = self._an_build_columns()
            column_keys = [c["key"] for c in columns]
            current = next((p for p in periods if p.get("is_current")), periods[0] if periods else {})
            date_from = None if balance_as_of else current.get("date_from")
            date_to = current.get("date_to")
            column_balances = self._an_column_balances_map(
                accounts, columns, date_from, date_to, display_account, flip_income=flip_income
            )
        else:
            columns = periods
            column_keys = [p["key"] for p in periods]
            column_balances = self._pl_period_balances_map(
                accounts, periods, display_account, balance_as_of=balance_as_of
            )
        total_by_period = self._pl_sum_balances(column_balances, column_keys)
        accounts_rows = self._pl_accounts_payload(accounts, column_balances, column_keys)
        hierarchy = []
        if use_hierarchy and accounts_rows:
            hierarchy = self._pl_build_group_hierarchy(accounts, column_balances, column_keys)
            if hierarchy and self._pl_hierarchy_too_flat(hierarchy):
                hierarchy = self._pl_build_code_prefix_hierarchy(accounts, column_balances, column_keys)
        return {
            "accounts": accounts_rows,
            "hierarchy": hierarchy,
            "use_hierarchy": bool(use_hierarchy and hierarchy),
            "total_by_period": total_by_period,
            "total": total_by_period.get(self._an_primary_key(), 0.0),
        }
