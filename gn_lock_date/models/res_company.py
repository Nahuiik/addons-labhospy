# -*- coding: utf-8 -*-

from datetime import date

from odoo import fields, models

from odoo.addons.account.models.company import LOCK_DATE_FIELDS


class ResCompany(models.Model):
    _inherit = "res.company"

    def get_all_lock_summary(self):
        """Return JSON-serializable lock overview for the Lock Dates dashboard (CE).

        Uses native ``res.company`` lock dates, ``account.lock_exception`` and
        granular ``gn.period.lock`` rules. Security: follows current user ACLs.

        Must remain a public method name (no leading underscore): OWL ``orm.call``
        invokes RPC and Odoo rejects private methods remotely.
        """
        self.ensure_one()
        company = self.sudo(False)

        def _fmt(d):
            if not d or d == date.min:
                return False
            return fields.Date.to_string(d)

        locks = []
        for fname in LOCK_DATE_FIELDS:
            user_fname = f"user_{fname}"
            stored = company[fname]
            effective = company[user_fname]
            eff_disp = _fmt(effective)
            sto_disp = _fmt(stored) if stored else False
            locks.append(
                {
                    "field": fname,
                    "label": company.fields_get([fname])[fname]["string"],
                    "stored": sto_disp,
                    "effective": eff_disp,
                    "exception_adjusted": bool(
                        sto_disp and eff_disp and stored != effective
                    ),
                }
            )

        Exception = self.env["account.lock_exception"]
        PeriodLock = self.env["gn.period.lock"]
        exc_domain = [
            ("company_id", "child_of", company.id),
            ("state", "=", "active"),
        ]
        ex_count = Exception.search_count(exc_domain)

        user = self.env.user
        return {
            "company_id": company.id,
            "company_name": company.display_name,
            "locks": locks,
            "exception_count": ex_count,
            "exceptions": Exception.gn_get_active_for_dashboard(company.id),
            "period_locks": PeriodLock._get_dashboard_summary(company.id),
            "permissions": {
                "can_update_lock_dates": user.has_group(
                    "account.group_account_manager"
                ),
                "can_revoke_exceptions": user.has_group(
                    "account.group_account_manager"
                ),
                "can_manage_period_locks": user.has_group(
                    "gn_lock_date.group_period_lock_user"
                ),
                "can_unlock_period": user.has_group(
                    "gn_lock_date.group_period_lock_unlock"
                ),
            },
        }
