# -*- coding: utf-8 -*-
from calendar import monthrange
from collections import Counter
from datetime import date, timedelta
from statistics import mean

from dateutil.relativedelta import relativedelta

from odoo import _, fields, http
from odoo.exceptions import AccessError
from odoo.http import request


class GnHrDashboardController(http.Controller):
    """Datos del dashboard regional: sin sudo; compañías según user.company_ids."""

    def _allowed_company_ids(self):
        user = request.env.user
        ids = user.company_ids.ids
        if not ids:
            raise AccessError(_("No tiene compañías asignadas."))
        return ids

    @staticmethod
    def _is_module_installed(env, module_name):
        mod = env["ir.module.module"].sudo().search(
            [("name", "=", module_name)], limit=1
        )
        return bool(mod) and mod.state == "installed"

    def _user_can_regional(self, user):
        if user.has_group("gn_hr_dashboard.group_gn_hr_dashboard_regional"):
            return True
        if self._is_module_installed(user.env, "gn_hr_intercompany"):
            return user.has_group(
                "gn_hr_intercompany.group_hr_intercompany_regional_manager"
            )
        return False

    def _headcount_at_date(self, Emp, company_ids, as_of_date):
        """Plantilla al cierre de as_of_date: alta ≤ fecha y (activo o baja posterior)."""
        return Emp.with_context(active_test=False).search_count([
            ("company_id", "in", company_ids),
            ("contract_date_start", "!=", False),
            ("contract_date_start", "<=", as_of_date),
            "|",
            ("active", "=", True),
            "&",
            ("active", "=", False),
            ("departure_date", ">", as_of_date),
        ])

    def _headcount_by_company(self, Emp, companies, company_ids):
        domain = [("company_id", "in", company_ids), ("active", "=", True)]
        groups = Emp._read_group(domain, ["company_id"], ["__count"])
        count_by = {}
        for company, count in groups:
            if company:
                count_by[company.id] = int(count)
        return [
            {
                "company": c.name,
                "company_id": c.id,
                "count": count_by.get(c.id, 0),
            }
            for c in companies
        ]

    def _payroll_gross_totals(self, Payslip, company_ids, d0, d1):
        """Suma bruta de nómina por compañía y total (slips solapados al período)."""
        domain = [
            ("company_id", "in", company_ids),
            ("date_from", "<=", d1),
            ("date_to", ">=", d0),
            ("state", "in", ["done", "paid"]),
        ]
        groups = Payslip._read_group(domain, ["company_id"], ["gross_wage:sum"])
        by_company = {}
        total = 0.0
        for company, gross_sum in groups:
            if not company:
                continue
            cid = company.id
            amt = float(gross_sum or 0.0)
            by_company[cid] = amt
            total += amt
        return total, by_company

    def _country_options(self, env, company_ids):
        companies = env["res.company"].browse(company_ids)
        by_id = {}
        for comp in companies:
            c = comp.country_id
            if c:
                by_id[c.id] = {"id": c.id, "name": c.name}
        return sorted(by_id.values(), key=lambda x: x["name"])

    def _filter_companies_by_country(self, env, company_ids, country_id):
        if not country_id:
            return company_ids
        try:
            cid = int(country_id)
        except (TypeError, ValueError):
            return company_ids
        companies = env["res.company"].browse(company_ids).filtered(
            lambda c: c.country_id and c.country_id.id == cid
        )
        return companies.ids

    def _parse_int(self, value, default):
        if value in (None, "", False):
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _resolve_period(self, env, year, month, date_from_str, date_to_str):
        """Devuelve (date_from, date_to, mode) con mode 'range' o 'month'."""
        today = fields.Date.context_today(env["hr.employee"])
        if date_from_str and date_to_str:
            d0 = fields.Date.to_date(str(date_from_str))
            d1 = fields.Date.to_date(str(date_to_str))
            if d0 > d1:
                d0, d1 = d1, d0
            return d0, d1, "range"
        y = self._parse_int(year, today.year)
        m = self._parse_int(month, today.month)
        y = max(2000, min(2100, y))
        m = max(1, min(12, m))
        last = monthrange(y, m)[1]
        d0 = date(y, m, 1)
        d1 = date(y, m, last)
        return d0, d1, "month"

    @staticmethod
    def _previous_calendar_month_bounds(period_start):
        """Mes calendario completo anterior al que contiene period_start."""
        first_of_month = period_start.replace(day=1)
        end_prev = first_of_month - relativedelta(days=1)
        start_prev = end_prev.replace(day=1)
        return start_prev, end_prev

    def _absence_by_leave_type(self, Leave, company_ids, period_start, period_end):
        """Días de ausencia validados agrupados por tipo de permiso."""
        domain = [
            ("company_id", "in", company_ids),
            ("state", "=", "validate"),
            ("date_from", "<=", period_end),
            ("date_to", ">=", period_start),
        ]
        groups = Leave._read_group(
            domain, ["holiday_status_id"], ["number_of_days:sum"]
        )
        rows = []
        for leave_type, days_sum in groups:
            name = (
                leave_type.display_name
                if leave_type
                else _("Sin tipo")
            )
            tid = leave_type.id if leave_type else None
            days = float(days_sum or 0.0)
            rows.append(
                {"leave_type_id": tid, "name": name, "days": round(days, 2)}
            )
        rows.sort(key=lambda x: -x["days"])
        return rows

    def _diversity_by_sex(self, Emp, company_ids):
        """Conteo de plantilla activa por valor del campo sex (si existe en el modelo)."""
        if "sex" not in Emp._fields:
            return []
        domain = [
            ("company_id", "in", company_ids),
            ("active", "=", True),
        ]
        groups = Emp._read_group(domain, ["sex"], ["__count"])
        out = []
        selection = dict(Emp._fields["sex"]._description_selection(Emp.env))
        for sex_key, count in groups:
            if sex_key is None or sex_key is False:
                label = _("Sin dato")
            else:
                label = (
                    selection.get(str(sex_key))
                    or selection.get(sex_key)
                    or str(sex_key)
                )
            out.append(
                {
                    "sex": sex_key or False,
                    "label": label,
                    "count": int(count),
                }
            )
        out.sort(key=lambda x: -x["count"])
        return out

    @staticmethod
    def _tenure_band_label(years):
        if years < 1:
            return "<1"
        if years < 3:
            return "1-3"
        if years < 5:
            return "3-5"
        if years < 10:
            return "5-10"
        return "10+"

    def _tenure_bands(self, starts_years_list):
        """Distribución de antigüedad en bandas (años desde inicio de contrato)."""
        order = ["<1", "1-3", "3-5", "5-10", "10+"]
        counts = Counter(self._tenure_band_label(y) for y in starts_years_list)
        return [{"band": b, "count": counts.get(b, 0)} for b in order]

    def _sum_overtime_hours(self, env, company_ids, d0, d1):
        if "gn.hn.hr.attendance.incident" not in env:
            return 0.0
        Incident = env["gn.hn.hr.attendance.incident"]
        recs = Incident.search([
            ("company_id", "in", company_ids),
            ("incident_type", "=", "overtime"),
            ("state", "in", ["approved", "applied"]),
            ("date", ">=", d0),
            ("date", "<=", d1),
        ])
        return round(sum(r.overtime_hours or 0.0 for r in recs), 1)

    def _recruitment_payload(self, env, company_ids, period_start, period_end):
        """Métricas de puestos (hr.job) y, si está instalado hr_recruitment, contrataciones."""
        Job = env["hr.job"]
        jobs = Job.search([
            ("company_id", "in", company_ids),
            ("active", "=", True),
            ("no_of_recruitment", ">", 0),
        ])
        payload = {
            "hr_recruitment_installed": False,
            "jobs_recruiting": len(jobs),
            "recruitment_target_sum": int(sum(jobs.mapped("no_of_recruitment"))),
            "hired_in_period": 0,
            "avg_days_to_hire": None,
        }
        if not self._is_module_installed(env, "hr_recruitment"):
            return payload
        if "hr.applicant" not in env:
            return payload
        payload["hr_recruitment_installed"] = True
        Applicant = env["hr.applicant"]
        dt_start = fields.Datetime.to_datetime(period_start)
        dt_end_excl = fields.Datetime.to_datetime(period_end) + timedelta(days=1)
        hired_domain = [
            ("company_id", "in", company_ids),
            ("date_closed", "!=", False),
            ("date_closed", ">=", fields.Datetime.to_string(dt_start)),
            ("date_closed", "<", fields.Datetime.to_string(dt_end_excl)),
        ]
        hired = Applicant.search(hired_domain)
        payload["hired_in_period"] = len(hired)
        durations = []
        for app in hired:
            if app.create_date and app.date_closed:
                delta = app.date_closed - app.create_date
                durations.append(delta.total_seconds() / 86400.0)
        if durations:
            payload["avg_days_to_hire"] = round(mean(durations), 1)
        return payload

    def _movement_trend(self, env, company_ids, end_date, months=12):
        """Serie mensual de altas, bajas y headcount al cierre de cada mes."""
        Emp = env["hr.employee"]
        trend = []
        for i in range(months - 1, -1, -1):
            m_end = end_date.replace(day=1) - relativedelta(months=i)
            m_end = m_end + relativedelta(months=1, days=-1)
            m_start = m_end.replace(day=1)
            hires = Emp.search_count([
                ("company_id", "in", company_ids),
                ("contract_date_start", ">=", m_start),
                ("contract_date_start", "<=", m_end),
            ])
            departures = Emp.with_context(active_test=False).search_count([
                ("company_id", "in", company_ids),
                ("active", "=", False),
                ("departure_date", ">=", m_start),
                ("departure_date", "<=", m_end),
            ])
            headcount_end = self._headcount_at_date(Emp, company_ids, m_end)
            trend.append({
                "month": m_start.strftime("%Y-%m"),
                "hires": hires,
                "departures": departures,
                "headcount_end": headcount_end,
            })
        return trend

    def _payroll_trend_months(self, env, company_ids, companies, end_date, num_months=6):
        Payslip = env["hr.payslip"]
        trend = []
        for i in range(num_months - 1, -1, -1):
            m_start = end_date.replace(day=1) - relativedelta(months=i)
            m_end = m_start + relativedelta(months=1, days=-1)
            label = m_start.strftime("%Y-%m")
            month_data = {"month": label}
            for comp in companies:
                slips = Payslip.search([
                    ("company_id", "=", comp.id),
                    ("date_from", ">=", m_start),
                    ("date_to", "<=", m_end),
                    ("state", "in", ["done", "paid"]),
                ])
                month_data[comp.name] = round(
                    sum(s.gross_wage for s in slips), 2
                )
            trend.append(month_data)
        return trend

    def _payroll_per_employee_trend(self, env, company_ids, end_date, num_months=6):
        """Bruto de nómina del mes calendario completo / headcount al último día del mes."""
        Payslip = env["hr.payslip"]
        Emp = env["hr.employee"]
        trend = []
        for i in range(num_months - 1, -1, -1):
            m_start = end_date.replace(day=1) - relativedelta(months=i)
            m_end = m_start + relativedelta(months=1, days=-1)
            label = m_start.strftime("%Y-%m")
            slips = Payslip.search([
                ("company_id", "in", company_ids),
                ("date_from", ">=", m_start),
                ("date_to", "<=", m_end),
                ("state", "in", ["done", "paid"]),
            ])
            total = round(sum(s.gross_wage for s in slips), 2)
            hc = self._headcount_at_date(Emp, company_ids, m_end)
            value = round(total / hc, 2) if hc else None
            trend.append({"month": label, "value": value})
        return trend

    def _contract_type_distribution(self, Emp, company_ids):
        if "contract_type_id" not in Emp._fields:
            return []
        domain = [
            ("company_id", "in", company_ids),
            ("active", "=", True),
        ]
        groups = Emp._read_group(domain, ["contract_type_id"], ["__count"])
        rows = []
        for ctype, count in groups:
            tid = ctype.id if ctype else None
            name = ctype.display_name if ctype else _("Sin tipo")
            rows.append({
                "type_id": tid,
                "name": name,
                "count": int(count),
            })
        rows.sort(key=lambda x: -x["count"])
        return rows

    def _contract_type_monthly(self, env, company_ids, end_date, months=12):
        """Headcount al cierre de cada mes por tipo de contrato (campo actual del empleado)."""
        Emp = env["hr.employee"]
        if "contract_type_id" not in Emp._fields:
            return {"months": [], "series": []}

        months_labels = []
        per_month = []
        for i in range(months - 1, -1, -1):
            m_anchor = end_date.replace(day=1) - relativedelta(months=i)
            m_end = m_anchor + relativedelta(months=1, days=-1)
            m_start = m_end.replace(day=1)
            months_labels.append(m_start.strftime("%Y-%m"))
            domain = [
                ("company_id", "in", company_ids),
                ("contract_date_start", "!=", False),
                ("contract_date_start", "<=", m_end),
                "|",
                ("active", "=", True),
                "&",
                ("active", "=", False),
                ("departure_date", ">", m_end),
            ]
            groups = Emp._read_group(domain, ["contract_type_id"], ["__count"])
            counts = {}
            for ctype, count in groups:
                tid = ctype.id if ctype else False
                counts[tid] = int(count)
            per_month.append(counts)

        all_ids = set()
        for c in per_month:
            all_ids.update(c.keys())
        series = []
        ContractType = env["hr.contract.type"]
        for tid in sorted(all_ids, key=lambda x: (x is False, x or 0)):
            if tid is False:
                label = _("Sin tipo")
            else:
                label = ContractType.browse(tid).name or str(tid)
            series.append({
                "type_id": tid,
                "name": label,
                "data": [c.get(tid, 0) for c in per_month],
            })
        return {"months": months_labels, "series": series}

    def _empty_payload(self, country_options, country_id, period_start, period_end, period_mode, warning):
        z = {
            "headcount": 0,
            "payroll_cost": 0.0,
            "payroll_cost_per_employee": 0.0,
            "turnover_rate": 0.0,
            "absence_rate": 0.0,
            "absence_days": 0.0,
            "overtime_hours": 0.0,
            "overtime_prev_month_hours": 0.0,
            "overtime_variation_pct": None,
            "leave_balance": 0.0,
            "late_count": 0,
            "payroll_prev_month": 0.0,
            "payroll_variation_pct": None,
            "movement_net": 0,
            "avg_tenure_years": 0.0,
        }
        return {
            "company_names": [],
            "kpis": z,
            "absence_by_type": [],
            "diversity_by_sex": [],
            "tenure_bands": [],
            "recruitment": {
                "hr_recruitment_installed": False,
                "jobs_recruiting": 0,
                "recruitment_target_sum": 0,
                "hired_in_period": 0,
                "avg_days_to_hire": None,
            },
            "contracts_expiring": {"d30": 0, "d60": 0, "d90": 0},
            "headcount_by_company": [],
            "payroll_by_company": [],
            "payroll_trend": [],
            "payroll_per_employee_trend": [],
            "incident_distribution": [],
            "movement_trend": [],
            "contract_type_distribution": [],
            "contract_type_monthly": {"months": [], "series": []},
            "pending_alerts": {
                "contracts_expiring": 0,
                "pending_incidents": 0,
            },
            "filter_options": {"countries": country_options},
            "applied_filters": {
                "country_id": country_id,
                "year": period_start.year if period_mode == "month" else None,
                "month": period_start.month if period_mode == "month" else None,
                "date_from": fields.Date.to_string(period_start)
                if period_mode == "range"
                else None,
                "date_to": fields.Date.to_string(period_end)
                if period_mode == "range"
                else None,
                "period_mode": period_mode,
            },
            "drilldown": {},
            "warning": warning,
        }

    @http.route("/gn_hr_dashboard/regional", type="jsonrpc", auth="user")
    def get_regional_dashboard_data(
        self,
        country_id=None,
        year=None,
        month=None,
        date_from=None,
        date_to=None,
    ):
        env = request.env
        user = env.user
        if not self._user_can_regional(user):
            raise AccessError(
                _("No tiene permisos para acceder al dashboard regional.")
            )
        base_company_ids = self._allowed_company_ids()
        country_options = self._country_options(env, base_company_ids)
        company_ids = self._filter_companies_by_country(
            env, base_company_ids, country_id
        )
        period_start, period_end, period_mode = self._resolve_period(
            env, year, month, date_from, date_to
        )
        turnover_window_start = period_end - relativedelta(months=12)

        warning = None
        if not company_ids:
            warning = _("No hay compañías que coincidan con el filtro de país.")
            return self._empty_payload(
                country_options,
                country_id,
                period_start,
                period_end,
                period_mode,
                warning,
            )

        Emp = env["hr.employee"]
        Payslip = env["hr.payslip"]
        Leave = env["hr.leave"]
        Alloc = env["hr.leave.allocation"]
        companies = env["res.company"].browse(company_ids)

        total_headcount = Emp.search_count([
            ("company_id", "in", company_ids),
            ("active", "=", True),
        ])

        headcount_by_company = self._headcount_by_company(
            Emp, companies, company_ids
        )

        pm_start, pm_end = self._previous_calendar_month_bounds(period_start)
        payroll_cost, pay_by_cid = self._payroll_gross_totals(
            Payslip, company_ids, period_start, period_end
        )
        payroll_prev, _prev_by_cid = self._payroll_gross_totals(
            Payslip, company_ids, pm_start, pm_end
        )
        if payroll_prev > 0:
            payroll_variation_pct = round(
                (payroll_cost - payroll_prev) / payroll_prev * 100, 1
            )
        elif payroll_cost > 0:
            payroll_variation_pct = None
        else:
            payroll_variation_pct = 0.0

        payroll_cost_per_employee = (
            round(payroll_cost / total_headcount, 2) if total_headcount else 0.0
        )

        payroll_by_company = [
            {
                "company": comp.name,
                "cost": round(pay_by_cid.get(comp.id, 0.0), 2),
            }
            for comp in companies
        ]

        payroll_trend = self._payroll_trend_months(
            env, company_ids, companies, period_end, num_months=6
        )
        payroll_per_employee_trend = self._payroll_per_employee_trend(
            env, company_ids, period_end, num_months=6
        )

        departed = Emp.with_context(active_test=False).search_count([
            ("company_id", "in", company_ids),
            ("active", "=", False),
            ("departure_date", ">=", turnover_window_start),
            ("departure_date", "<=", period_end),
        ])
        avg_hc = total_headcount or 1
        turnover_rate = round((departed / avg_hc) * 100, 1)

        absence_days = 0.0
        leaves = Leave.search([
            ("company_id", "in", company_ids),
            ("state", "=", "validate"),
            ("date_from", "<=", period_end),
            ("date_to", ">=", period_start),
        ])
        for lv in leaves:
            absence_days += lv.number_of_days or 0.0
        work_days = total_headcount * 22 or 1
        absence_rate = round((absence_days / work_days) * 100, 1)
        absence_by_type = self._absence_by_leave_type(
            Leave, company_ids, period_start, period_end
        )

        diversity_by_sex = self._diversity_by_sex(Emp, company_ids)

        hires_period = Emp.search_count([
            ("company_id", "in", company_ids),
            ("contract_date_start", ">=", period_start),
            ("contract_date_start", "<=", period_end),
        ])
        departures_period = Emp.with_context(active_test=False).search_count([
            ("company_id", "in", company_ids),
            ("active", "=", False),
            ("departure_date", ">=", period_start),
            ("departure_date", "<=", period_end),
        ])
        movement_net = hires_period - departures_period

        today_ctx = fields.Date.context_today(env["hr.employee"])
        starts_data = Emp.search_read(
            [
                ("company_id", "in", company_ids),
                ("active", "=", True),
                ("contract_date_start", "!=", False),
            ],
            ["contract_date_start"],
        )
        years_list = []
        if starts_data:
            for row in starts_data:
                d_start = fields.Date.to_date(row["contract_date_start"])
                years_list.append((today_ctx - d_start).days / 365.25)
            avg_tenure_years = round(mean(years_list), 2)
        else:
            avg_tenure_years = 0.0
        tenure_bands = self._tenure_bands(years_list)

        d30_end = today_ctx + relativedelta(days=30)
        d60_end = today_ctx + relativedelta(days=60)
        d90_end = today_ctx + relativedelta(days=90)
        base_contract = [
            ("active", "=", True),
            ("company_id", "in", company_ids),
            ("contract_date_end", "!=", False),
        ]
        contracts_d30 = Emp.search_count(
            base_contract
            + [
                ("contract_date_end", ">=", today_ctx),
                ("contract_date_end", "<=", d30_end),
            ]
        )
        contracts_d60 = Emp.search_count(
            base_contract
            + [
                ("contract_date_end", ">", d30_end),
                ("contract_date_end", "<=", d60_end),
            ]
        )
        contracts_d90 = Emp.search_count(
            base_contract
            + [
                ("contract_date_end", ">", d60_end),
                ("contract_date_end", "<=", d90_end),
            ]
        )

        overtime_hours = self._sum_overtime_hours(
            env, company_ids, period_start, period_end
        )
        overtime_prev_month_hours = self._sum_overtime_hours(
            env, company_ids, pm_start, pm_end
        )
        if overtime_prev_month_hours > 0:
            overtime_variation_pct = round(
                (overtime_hours - overtime_prev_month_hours)
                / overtime_prev_month_hours
                * 100,
                1,
            )
        elif overtime_hours > 0:
            overtime_variation_pct = None
        else:
            overtime_variation_pct = 0.0

        incident_distribution = []
        pending_incidents_count = 0
        late_count = 0
        if "gn.hn.hr.attendance.incident" in env:
            Incident = env["gn.hn.hr.attendance.incident"]
            late_count = Incident.search_count([
                ("company_id", "in", company_ids),
                ("incident_type", "=", "late"),
                ("date", ">=", period_start),
                ("date", "<=", period_end),
            ])
            all_incidents = Incident.search([
                ("company_id", "in", company_ids),
                ("date", ">=", period_start),
                ("date", "<=", period_end),
                ("incident_type", "!=", "none"),
            ])
            incident_types = {}
            for inc in all_incidents:
                t = inc.incident_type
                incident_types[t] = incident_types.get(t, 0) + 1
            incident_distribution = [
                {"type": k, "count": v} for k, v in incident_types.items()
            ]
            pending_incidents_count = Incident.search_count([
                ("company_id", "in", company_ids),
                ("state", "=", "pending"),
            ])

        allocations = Alloc.search([
            ("employee_id.company_id", "in", company_ids),
            ("employee_id.active", "=", True),
            ("state", "=", "validate"),
        ])
        total_leave_balance = sum(
            max(a.number_of_days - a.leaves_taken, 0) for a in allocations
        )

        emp_domain_ids = Emp.search(
            [
                ("company_id", "in", company_ids),
                ("active", "=", True),
            ]
        ).ids
        pending_activities = 0
        if emp_domain_ids:
            pending_activities = env["mail.activity"].search_count([
                ("res_model", "=", "hr.employee"),
                ("res_id", "in", emp_domain_ids),
                ("summary", "ilike", "Contrato por vencer"),
            ])

        movement_trend = self._movement_trend(
            env, company_ids, period_end, months=12
        )
        contract_type_distribution = self._contract_type_distribution(
            Emp, company_ids
        )
        contract_type_monthly = self._contract_type_monthly(
            env, company_ids, period_end, months=12
        )

        recruitment = self._recruitment_payload(
            env, company_ids, period_start, period_end
        )

        drilldown = {
            "employee_contract_expiring": {
                "today": fields.Date.to_string(today_ctx),
                "end_90": fields.Date.to_string(d90_end),
                "company_ids": list(company_ids),
            },
        }

        return {
            "company_names": companies.mapped("name"),
            "kpis": {
                "headcount": total_headcount,
                "payroll_cost": round(payroll_cost, 2),
                "payroll_cost_per_employee": payroll_cost_per_employee,
                "turnover_rate": turnover_rate,
                "absence_rate": absence_rate,
                "absence_days": round(absence_days, 2),
                "overtime_hours": overtime_hours,
                "overtime_prev_month_hours": overtime_prev_month_hours,
                "overtime_variation_pct": overtime_variation_pct,
                "leave_balance": round(total_leave_balance, 1),
                "late_count": late_count,
                "payroll_prev_month": round(payroll_prev, 2),
                "payroll_variation_pct": payroll_variation_pct,
                "movement_net": movement_net,
                "avg_tenure_years": avg_tenure_years,
            },
            "absence_by_type": absence_by_type,
            "diversity_by_sex": diversity_by_sex,
            "tenure_bands": tenure_bands,
            "recruitment": recruitment,
            "contracts_expiring": {
                "d30": contracts_d30,
                "d60": contracts_d60,
                "d90": contracts_d90,
            },
            "headcount_by_company": headcount_by_company,
            "payroll_by_company": payroll_by_company,
            "payroll_trend": payroll_trend,
            "payroll_per_employee_trend": payroll_per_employee_trend,
            "incident_distribution": incident_distribution,
            "movement_trend": movement_trend,
            "contract_type_distribution": contract_type_distribution,
            "contract_type_monthly": contract_type_monthly,
            "pending_alerts": {
                "contracts_expiring": pending_activities,
                "pending_incidents": pending_incidents_count,
            },
            "filter_options": {"countries": country_options},
            "applied_filters": {
                "country_id": country_id,
                "year": period_start.year if period_mode == "month" else None,
                "month": period_start.month if period_mode == "month" else None,
                "date_from": fields.Date.to_string(period_start)
                if period_mode == "range"
                else None,
                "date_to": fields.Date.to_string(period_end)
                if period_mode == "range"
                else None,
                "period_mode": period_mode,
            },
            "drilldown": drilldown,
            "warning": warning,
        }
