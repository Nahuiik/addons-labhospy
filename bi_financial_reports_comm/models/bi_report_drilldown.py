# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

"""Utilidades para abrir account.move.line desde informes BI (drill-down)."""

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.tools.date_utils import get_fiscal_year, get_month, get_quarter


class BiReportDrilldownHelper(models.AbstractModel):
    _name = "bi.report.drilldown.helper"
    _description = "Helper drill-down a apuntes desde informes financieros BI"

    # Odoo 19+: display_type is always set (tax, product, …); exclude layout lines only.
    AML_LAYOUT_DISPLAY_TYPES = ("line_section", "line_subsection", "line_note")

    @api.model
    def aml_display_type_domain(self):
        return [("display_type", "not in", self.AML_LAYOUT_DISPLAY_TYPES)]

    @api.model
    def _period_dates_from_options(self, options):
        df = options.get("date_from")
        dt = options.get("date_to")
        if isinstance(df, str):
            df = fields.Date.from_string(df)
        if isinstance(dt, str):
            dt = fields.Date.from_string(dt)
        return df, dt

    @api.model
    def _get_comparison_period_dict(self, options):
        """Un único período comparativo (misma lógica que cash_flow_report)."""
        date_from, date_to = self._period_dates_from_options(options)
        if not date_from or not date_to:
            return None
        comparison_filter = options.get("comparison_filter") or "no_comparison"
        number_period = options.get("comparison_number_period", 1) or 1
        date_filter_type = options.get("date_filter_type") or "month"
        if comparison_filter in ("no_comparison", None, ""):
            return None
        if comparison_filter != "specific_date" and not number_period:
            return None
        if comparison_filter == "previous_period":
            pt = date_filter_type or "month"
            if pt == "month":
                cmp_to = date_to - relativedelta(months=number_period)
                cmp_from, cmp_to = get_month(cmp_to)
            elif pt == "quarter":
                cmp_to = date_to - relativedelta(months=3 * number_period)
                cmp_from, cmp_to = get_quarter(cmp_to)
            else:
                cmp_to = date_to - relativedelta(years=number_period)
                cmp_from, cmp_to = get_fiscal_year(cmp_to)
            return {
                "date_from": cmp_from.strftime("%Y-%m-%d"),
                "date_to": cmp_to.strftime("%Y-%m-%d"),
                "string": cmp_from.strftime("%d/%m/%Y") + " - " + cmp_to.strftime("%d/%m/%Y"),
            }
        if comparison_filter == "same_last_year":
            cmp_from = date_from - relativedelta(years=number_period)
            cmp_to = date_to - relativedelta(years=number_period)
            return {
                "date_from": cmp_from.strftime("%Y-%m-%d"),
                "date_to": cmp_to.strftime("%Y-%m-%d"),
                "string": cmp_from.strftime("%d/%m/%Y") + " - " + cmp_to.strftime("%d/%m/%Y"),
            }
        if comparison_filter == "specific_date":
            cmp_date_to = options.get("comparison_date_to")
            if cmp_date_to:
                cmp_to = fields.Date.from_string(cmp_date_to) if isinstance(cmp_date_to, str) else cmp_date_to
                pt = date_filter_type or "month"
                if pt == "month":
                    cmp_from, cmp_to = get_month(cmp_to)
                elif pt == "quarter":
                    cmp_from, cmp_to = get_quarter(cmp_to)
                else:
                    cmp_from, cmp_to = get_fiscal_year(cmp_to)
                return {
                    "date_from": cmp_from.strftime("%Y-%m-%d"),
                    "date_to": cmp_to.strftime("%Y-%m-%d"),
                    "string": cmp_from.strftime("%d/%m/%Y") + " - " + cmp_to.strftime("%d/%m/%Y"),
                }
        return None

    @api.model
    def resolve_drilldown_dates(self, options):
        """Resuelve fechas del drill-down; admite override drill_date_* (p. ej. tax por columna)."""
        ddf = options.get("drill_date_from")
        ddt = options.get("drill_date_to")
        if ddf and ddt:
            return (
                fields.Date.from_string(ddf) if isinstance(ddf, str) else ddf,
                fields.Date.from_string(ddt) if isinstance(ddt, str) else ddt,
            )
        drill_period = options.get("drill_period") or "current"
        date_from, date_to = self._period_dates_from_options(options)
        if drill_period != "comparison":
            return date_from, date_to
        cmp_p = self._get_comparison_period_dict(options)
        if cmp_p:
            return (
                fields.Date.from_string(cmp_p["date_from"]),
                fields.Date.from_string(cmp_p["date_to"]),
            )
        return date_from, date_to

    @api.model
    def aml_domain(self, options, account_id=None, extra_domain=None):
        date_from, date_to = self.resolve_drilldown_dates(options)
        company = self.env.company
        target_move = options.get("target_move") or "all"
        domain = [
            ("company_id", "=", company.id),
            *self.aml_display_type_domain(),
        ]
        if target_move == "posted":
            domain.append(("parent_state", "=", "posted"))
        else:
            domain.append(("parent_state", "in", ["draft", "posted"]))
        if date_from:
            domain.append(("date", ">=", date_from))
        if date_to:
            domain.append(("date", "<=", date_to))
        journal_ids = options.get("journal_ids") or []
        if journal_ids:
            domain.append(("journal_id", "in", journal_ids))
        if account_id is not None:
            domain.append(("account_id", "=", int(account_id)))
        if extra_domain:
            domain.extend(extra_domain)
        return domain

    @api.model
    def action_aml_window(self, domain, name=None):
        view = self.env.ref("account.view_move_line_tree_grouped_general", raise_if_not_found=False)
        list_view_id = view.id if view else False
        return {
            "type": "ir.actions.act_window",
            "name": name or _("Apuntes contables"),
            "res_model": "account.move.line",
            "views": [(list_view_id, "list"), (False, "form")],
            "view_mode": "list",
            "domain": domain,
            "target": "current",
            "context": {"search_default_group_by_move": 0},
        }
