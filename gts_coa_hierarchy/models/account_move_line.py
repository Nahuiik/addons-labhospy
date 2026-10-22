# -*- coding: utf-8 -*-
import ast

from odoo import api, models, _
from odoo.exceptions import ValidationError


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.constrains("account_id", "display_type")
    def _check_account_not_view(self):
        """Impide registrar apuntes en cuentas de mayor (tipo 'view').

        Las cuentas 'view' solo agrupan/encabezan la jerarquía del plan; no son
        imputables. Si se intenta usar una en un apunte real se bloquea y se pide
        usar una de sus subcuentas.
        """
        for line in self:
            account = line.account_id
            if account and account.account_type == "view":
                raise ValidationError(_(
                    "No se puede registrar en la cuenta de mayor «%(code)s %(name)s»: "
                    "es una cuenta de tipo Vista (solo agrupa la jerarquía y no es "
                    "imputable). Utilice una de sus subcuentas.",
                    code=account.code or "",
                    name=account.name or "",
                ))

    @api.model
    def _build_coa_domain(self, domain=None):
        """Dominio reusable para balances jerárquicos e informes de plan."""
        context = dict(self.env.context)
        domain = list(domain or [])
        if not isinstance(domain, (list, tuple)):
            domain = ast.literal_eval(domain)
        date_field = "date_maturity" if context.get("aged_balance") else "date"
        if context.get("date_to"):
            domain.append((date_field, "<=", context["date_to"]))
        if context.get("date_from"):
            if not context.get("strict_range"):
                domain += [
                    "|",
                    (date_field, ">=", context["date_from"]),
                    ("account_id.include_initial_balance", "=", True),
                ]
            elif context.get("initial_bal"):
                domain.append((date_field, "<", context["date_from"]))
            else:
                domain.append((date_field, ">=", context["date_from"]))

        if context.get("journal_ids"):
            journal_ids = context["journal_ids"]
            if hasattr(journal_ids, "ids"):
                journal_ids = journal_ids.ids
            domain.append(("journal_id", "in", journal_ids))

        state = context.get("state")
        if state and state.lower() != "all":
            domain.append(("parent_state", "=", state))

        if context.get("company_id"):
            domain.append(("company_id", "=", context["company_id"]))
        elif context.get("allowed_company_ids"):
            allowed_companies = context["allowed_company_ids"]
            if hasattr(allowed_companies, "ids"):
                allowed_companies = allowed_companies.ids
            domain.append(("company_id", "in", allowed_companies))
        else:
            domain.append(("company_id", "=", self.env.company.id))

        if context.get("reconcile_date"):
            domain += [
                "|",
                ("reconciled", "=", False),
                "|",
                ("matched_debit_ids.max_date", ">", context["reconcile_date"]),
                ("matched_credit_ids.max_date", ">", context["reconcile_date"]),
            ]

        if context.get("account_tag_ids"):
            tag_ids = context["account_tag_ids"]
            if hasattr(tag_ids, "ids"):
                tag_ids = tag_ids.ids
            domain.append(("account_id.tag_ids", "in", tag_ids))

        if context.get("analytic_tag_ids"):
            analytic_tags = context["analytic_tag_ids"]
            if hasattr(analytic_tags, "ids"):
                analytic_tags = analytic_tags.ids
            domain += [
                "|",
                ("analytic_account_id.tag_ids", "in", analytic_tags),
                ("analytic_tag_ids", "in", analytic_tags),
            ]

        if context.get("analytic_account_ids"):
            analytic_accounts = context["analytic_account_ids"]
            if hasattr(analytic_accounts, "ids"):
                analytic_accounts = analytic_accounts.ids
            domain.append(("analytic_account_id", "in", analytic_accounts))

        if context.get("partner_ids"):
            partner_ids = context["partner_ids"]
            if hasattr(partner_ids, "ids"):
                partner_ids = partner_ids.ids
            domain.append(("partner_id", "in", partner_ids))

        if context.get("partner_categories"):
            categories = context["partner_categories"]
            if hasattr(categories, "ids"):
                categories = categories.ids
            domain.append(("partner_id.category_id", "in", categories))

        domain.append(
            (
                "display_type",
                "not in",
                ("line_section", "line_note", "line_subsection"),
            )
        )
        domain.append(("parent_state", "!=", "cancel"))
        return domain
