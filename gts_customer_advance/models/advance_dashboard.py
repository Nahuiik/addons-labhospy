# -*- coding: utf-8 -*-
"""
Dashboard de anticipos: datos por creador y cotizaciones vinculadas.
"""

from datetime import date, timedelta
from collections import defaultdict

from odoo import api, models, _


class GtsAdvanceDashboard(models.AbstractModel):
    _name = "gts.advance.dashboard"
    _description = "Dashboard de Anticipos"

    @api.model
    def get_filter_options(self):
        """Usuarios que han creado anticipos (para filtro por creador)."""
        Payment = self.env["account.payment"]
        payments = Payment.search([
            ("is_advance", "=", True),
            ("partner_type", "=", "customer"),
        ])
        user_ids = payments.mapped("create_uid").sorted(key=lambda u: u.name)
        return {
            "creators": [
                {"id": u.id, "name": u.name}
                for u in user_ids
            ],
        }

    @api.model
    def get_dashboard_data(self, filters):
        """Datos del dashboard: KPIs y tabla por creador."""
        Payment = self.env["account.payment"]
        Link = self.env["sale.order.advance.link"]

        date_from, date_to = self._resolve_dates(filters)
        creator_id = filters.get("creator_id") or False
        company_id = filters.get("company_id") or self.env.company.id

        domain = [
            ("is_advance", "=", True),
            ("partner_type", "=", "customer"),
            ("company_id", "=", company_id),
            ("date", ">=", date_from.isoformat()),
            ("date", "<=", date_to.isoformat()),
        ]
        if creator_id:
            domain.append(("create_uid", "=", creator_id))

        payments = Payment.search(domain, order="create_date desc")
        payment_ids = payments.ids

        # Links: payment_id -> sale_order_id
        links = Link.search([("payment_id", "in", payment_ids)])
        payment_to_orders = defaultdict(set)
        for link in links:
            payment_to_orders[link.payment_id.id].add(link.sale_order_id.id)

        # Agrupar por creador
        by_creator = defaultdict(lambda: {"count": 0, "amount": 0.0, "linked_orders": set()})
        total_amount = 0.0
        total_linked = 0

        for p in payments:
            uid = p.create_uid.id
            by_creator[uid]["count"] += 1
            by_creator[uid]["amount"] += p.amount
            total_amount += p.amount
            order_ids = payment_to_orders.get(p.id, set())
            by_creator[uid]["linked_orders"].update(order_ids)
            if order_ids:
                total_linked += 1

        rows = []
        for uid, data in sorted(by_creator.items(), key=lambda x: -x[1]["amount"]):
            user = self.env["res.users"].browse(uid)
            rows.append({
                "user_id": uid,
                "user_name": user.name or _("Sin asignar"),
                "advance_count": data["count"],
                "advance_amount": data["amount"],
                "linked_quotation_count": len(data["linked_orders"]),
            })

        kpis = {
            "total_advances": len(payments),
            "total_amount": total_amount,
            "advances_with_links": total_linked,
        }

        return {
            "kpis": kpis,
            "rows": rows,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        }

    @api.model
    def get_drilldown_action(self, filters, row_key=False, col_key=False):
        """Abrir anticipos o cotizaciones desde el dashboard."""
        date_from, date_to = self._resolve_dates(filters)
        creator_id = filters.get("creator_id") or False
        company_id = filters.get("company_id") or self.env.company.id

        domain = [
            ("is_advance", "=", True),
            ("partner_type", "=", "customer"),
            ("company_id", "=", company_id),
            ("date", ">=", date_from.isoformat()),
            ("date", "<=", date_to.isoformat()),
        ]
        if row_key and isinstance(row_key, int):
            domain.append(("create_uid", "=", row_key))
        elif creator_id:
            domain.append(("create_uid", "=", creator_id))

        return {
            "type": "ir.actions.act_window",
            "name": _("Abonos/Anticipos"),
            "res_model": "account.payment",
            "views": [[False, "list"], [False, "form"]],
            "domain": domain,
            "context": {"create": False},
        }

    def _resolve_dates(self, filters):
        """Retorna (date_from, date_to) desde los filtros."""
        period = filters.get("period", "this_month")
        date_from_str = filters.get("date_from")
        date_to_str = filters.get("date_to")

        today = date.today()
        if period == "custom" and date_from_str and date_to_str:
            return date.fromisoformat(date_from_str), date.fromisoformat(date_to_str)

        if period == "today":
            return today, today
        if period == "this_week":
            start = today - timedelta(days=today.weekday())
            return start, today
        if period == "this_quarter":
            q = (today.month - 1) // 3 + 1
            start = date(today.year, (q - 1) * 3 + 1, 1)
            return start, today
        if period == "this_year":
            return date(today.year, 1, 1), today

        # this_month por defecto
        start = date(today.year, today.month, 1)
        return start, today
