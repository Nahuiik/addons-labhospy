# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountLockException(models.Model):
    _inherit = "account.lock_exception"

    @api.model
    def gn_get_active_for_dashboard(self, company_id):
        """Serialize active lock exceptions for the dashboard table."""
        recs = self.search(
            [
                ("company_id", "=", company_id),
                ("state", "=", "active"),
            ],
            order="create_date desc",
            limit=50,
        )
        field_labels = dict(
            self.fields_get(["lock_date_field"])["lock_date_field"]["selection"]
        )
        out = []
        for rec in recs:
            out.append(
                {
                    "id": rec.id,
                    "user_id": rec.user_id.id if rec.user_id else False,
                    "user_name": rec.user_id.display_name if rec.user_id else "",
                    "lock_date_field": rec.lock_date_field,
                    "lock_date_field_label": field_labels.get(
                        rec.lock_date_field, rec.lock_date_field
                    ),
                    "lock_date": fields.Date.to_string(rec.lock_date)
                    if rec.lock_date
                    else False,
                    "reason": rec.reason or "",
                    "end_datetime": fields.Datetime.to_string(rec.end_datetime)
                    if rec.end_datetime
                    else False,
                }
            )
        return out
