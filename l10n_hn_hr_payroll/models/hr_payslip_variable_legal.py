# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

from calendar import monthrange
from datetime import date

from odoo import api, models


class HrPayslipVariableLegal(models.Model):
    _inherit = "hr.payslip"

    _HN_COMMISSION_INPUT_CODES = ("COMISIONES",)

    @api.model
    def _l10n_hn_prior_mtd_payslip_states(self):
        return ("validated", "paid", "done", "verify")

    def _l10n_hn_is_biweekly_hn_structure(self):
        """True si el recibo usa estructura quincenal HN."""
        self.ensure_one()
        if not self.struct_id:
            return False
        country = self.struct_id.country_id
        if country and country.code != "HN":
            return False
        st = self.struct_id.type_id
        return (getattr(st, "default_schedule_pay", None) or "") == "bi-weekly"

    def _l10n_hn_inputs_commission_amount(self, inputs):
        if not inputs:
            return 0.0
        total = 0.0
        for code in self._HN_COMMISSION_INPUT_CODES:
            if code in inputs:
                obj = inputs[code]
                amt = getattr(obj, "amount", None)
                if amt is not None:
                    total += float(amt or 0)
        return total

    def _l10n_hn_slip_commission_total(self, slip):
        total = 0.0
        for line in slip.line_ids:
            code = line.salary_rule_id.code if line.salary_rule_id else None
            if code in self._HN_COMMISSION_INPUT_CODES:
                total += float(line.total or 0)
        if total:
            return total
        for il in slip.input_line_ids:
            code = il.input_type_id.code if il.input_type_id else None
            if code in self._HN_COMMISSION_INPUT_CODES:
                total += float(il.amount or 0)
        return total

    def _l10n_hn_confirmed_month_prior_commission_total(self):
        total = 0.0
        for ps in self._l10n_hn_confirmed_hn_slips_same_calendar_month():
            total += self._l10n_hn_slip_commission_total(ps)
        return total

    def _l10n_hn_use_biweekly_real_mtd_legal(self, categories, inputs):
        self.ensure_one()
        if not self._l10n_hn_is_biweekly_hn_structure() or not self.employee_id:
            return False
        if self.employee_id.l10n_hn_variable_legal_monthly:
            return True
        if self._l10n_hn_inputs_commission_amount(inputs) > 0:
            return True
        if self._l10n_hn_confirmed_month_prior_commission_total() > 0:
            return True
        return False

    def _l10n_hn_use_split_quincena_payroll(self, categories, inputs):
        """Salario mensual 1.ª quincena + comisiones 2.ª (toggles HN del empleado)."""
        self.ensure_one()
        if not self._l10n_hn_is_biweekly_hn_structure() or not self.employee_id:
            return False
        employee = self.employee_id
        return (
            employee.l10n_hn_biweekly_pay_contract_first_half_only
            and employee.l10n_hn_variable_legal_monthly
        )

    def _l10n_hn_use_split_quincena_rap(self, categories, inputs):
        """Alias retrocompatible: RAP/ISR por quincena según toggles HN."""
        return self._l10n_hn_use_split_quincena_payroll(categories, inputs)

    def _l10n_hn_slip_gross_total(self, slip):
        line = slip.line_ids.filtered(lambda l: l.salary_rule_id.code == "GROSS")
        return float(line[:1].total or 0.0) if line else 0.0

    def _l10n_hn_isr_gross_tax_base(self, categories):
        if not categories:
            return 0.0
        gross_cat = float(categories.get("GROSS", 0) or 0.0)
        basic = float(categories.get("BASIC", 0) or 0.0)
        alw = float(categories.get("ALW", 0) or 0.0)
        return max(gross_cat, basic + alw)

    def _l10n_hn_confirmed_hn_slips_same_calendar_month(self):
        self.ensure_one()
        ref = self.date_to or self.date_from
        if not ref or not self.employee_id or not self.company_id:
            return self.env["hr.payslip"]
        y, m = ref.year, ref.month
        start = date(y, m, 1)
        end = date(y, m, monthrange(y, m)[1])
        dom = [
            ("employee_id", "=", self.employee_id.id),
            ("company_id", "=", self.company_id.id),
            ("state", "in", self._l10n_hn_prior_mtd_payslip_states()),
            ("date_from", "<=", end),
            ("date_to", ">=", start),
            ("struct_id.country_id.code", "=", "HN"),
            ("credit_note", "=", False),
        ]
        if self.ids:
            dom.append(("id", "not in", self.ids))
        return self.search(dom, order="date_from asc, id asc")

    def _l10n_hn_prior_slip_line_abs_total(self, rule_code):
        total = 0.0
        for ps in self._l10n_hn_confirmed_hn_slips_same_calendar_month():
            line = ps.line_ids.filtered(lambda l: l.salary_rule_id.code == rule_code)
            if line:
                total += abs(float(line[0].total or 0.0))
        return total

    def _l10n_hn_variable_legal_month_gross_mtd(self, current_gross):
        total = float(current_gross or 0.0)
        for ps in self._l10n_hn_confirmed_hn_slips_same_calendar_month():
            total += self._l10n_hn_slip_gross_total(ps)
        return total

    def _l10n_hn_variable_legal_month_rule_abs_mtd(self, rule_code, current_line_total):
        return self._l10n_hn_prior_slip_line_abs_total(rule_code) + abs(
            float(current_line_total or 0.0)
        )

    def _l10n_hn_biweekly_apply_in_skips_current_period(self, apply_in):
        self.ensure_one()
        normalized = apply_in or "both"
        if normalized == "both":
            return False
        day_start = self.date_from.day if self.date_from else 1
        is_first_half = day_start <= 15
        if normalized in ("first", "first_half") and not is_first_half:
            return True
        if normalized in ("second", "second_half") and is_first_half:
            return True
        return False

    def _l10n_hn_ihss_should_apply_this_period(self, ihss_settings):
        self.ensure_one()
        if not ihss_settings:
            return False
        include_in = ihss_settings.include_in or "both"
        if include_in == "both":
            if self.date_to and self.date_to.day <= 15:
                return ihss_settings.apply_first_quincena
            return ihss_settings.apply_second_quincena
        if self._l10n_hn_biweekly_apply_in_skips_current_period(include_in):
            return False
        if self.date_to and self.date_to.day <= 15:
            return ihss_settings.apply_first_quincena
        return ihss_settings.apply_second_quincena

    def _l10n_hn_get_ihss_settings(self):
        self.ensure_one()
        year = self.date_to.year if self.date_to else date.today().year
        return self.env["l10n.hn.ihss.settings"].search([
            ("year", "=", year),
            ("state", "=", "validated"),
            ("company_id", "=", self.company_id.id),
        ], limit=1)

    def _l10n_hn_compute_monthly_ihss_employee_due(self, month_gross, ihss_settings):
        if month_gross <= 0 or not ihss_settings:
            return 0.0
        ceiling_15 = ihss_settings.get_ceiling_for_period(15, "ivm")
        if month_gross >= ceiling_15 * 2:
            return ihss_settings.ihss_amount_monthly
        taxable_ivm = min(month_gross, ihss_settings.ivm_ceiling_monthly)
        taxable_em = min(month_gross, ihss_settings.em_ceiling_monthly)
        return round(
            taxable_ivm * (ihss_settings.ivm_employee_rate / 100.0)
            + taxable_em * (ihss_settings.em_employee_rate / 100.0),
            2,
        )

    def _l10n_hn_compute_basic_biweekly(self, version, employee, inputs):
        """Salario base quincenal HN (toggle «Contrato solo en 1.ª quincena»)."""
        self.ensure_one()
        ver = version or employee.current_version_id
        std = self.standard_period_days or 15
        cd = float(self.hn_contract_period_days or 0)
        wage_monthly = (ver.wage if ver else 0.0) or (employee.wage or 0.0)
        if not wage_monthly:
            return 0.0

        day_start = self.date_from.day if self.date_from else 1
        second_half = day_start >= 16

        if employee.l10n_hn_biweekly_pay_contract_first_half_only:
            if second_half:
                return 0.0
            if std:
                return wage_monthly * (cd / float(std))
            return wage_monthly

        if "DED_SAL_2DA" in inputs and second_half:
            return 0.0

        if std:
            return (wage_monthly / 2.0) * (cd / float(std))
        return wage_monthly / 2.0

    def _l10n_hn_get_rap_settings(self):
        self.ensure_one()
        year = self.date_to.year if self.date_to else date.today().year
        return self.env["l10n.hn.rap.settings"].search([
            ("year", "=", year),
            ("state", "=", "validated"),
            ("company_id", "=", self.company_id.id),
        ], limit=1)

    def _l10n_hn_rap_should_apply_this_period(self, rap_settings):
        """Respeta include_in de Establecer RAP y flags de quincena en ajustes RAP."""
        self.ensure_one()
        ver = self.version_id or self.employee_id.current_version_id
        if ver and ver.rap_setup_id and ver.rap_setup_id.include_in:
            if self._l10n_hn_biweekly_apply_in_skips_current_period(ver.rap_setup_id.include_in):
                return False
        if rap_settings:
            if self.date_to and self.date_to.day <= 15:
                return rap_settings.apply_first_quincena
            return rap_settings.apply_second_quincena
        return bool(
            ver
            and (
                (ver.rap_manual and ver.amount_rap_manual)
                or ver.rap_fee
                or ver.rap_foviif_amount_biweekly
            )
        )

    def _l10n_hn_compute_monthly_rap_employee_due(self, month_gross, rap_settings, ihss_settings, version):
        if month_gross <= 0:
            return 0.0
        if version and version.rap_setup_id:
            return version.rap_setup_id._compute_rap_fee_for_wage(month_gross)
        if not rap_settings or not ihss_settings:
            return 0.0
        ivm_ceiling = ihss_settings.ivm_ceiling_monthly or 0.0
        if month_gross <= ivm_ceiling:
            return 0.0
        foviif_base = max(
            0.0,
            min(month_gross - ivm_ceiling, rap_settings.foviif_floor_monthly),
        )
        return round(foviif_base * (rap_settings.foviif_employee_rate / 100.0), 2)

    def _l10n_hn_rap_techo_half_monthly(self, rap_settings, ihss_settings, version):
        """Mitad del techo RAP mensual (IVM / techo_rap_min) asignada a cada quincena."""
        if version and version.rap_setup_id:
            return (version.rap_setup_id.techo_rap_min or 0.0) / 2.0
        if ihss_settings:
            return (ihss_settings.ivm_ceiling_monthly or 0.0) / 2.0
        return 0.0

    def _l10n_hn_rap_rate_pct(self, rap_settings, version):
        if version and version.rap_setup_id:
            return version.rap_setup_id.rap_percentage or 1.5
        if rap_settings:
            return rap_settings.foviif_employee_rate or 1.5
        return 1.5

    def _l10n_hn_commission_amount_from_result_rules(self, result_rules):
        if not result_rules:
            return 0.0
        total = 0.0
        for code in self._HN_COMMISSION_INPUT_CODES:
            rule = result_rules.get(code)
            if rule:
                total += abs(float(rule.get("total", 0) or 0))
        return total

    def _l10n_hn_split_quincena_rap_period_income(self, categories, inputs, result_rules=None):
        """Ingreso gravable RAP del periodo: salario mensual (1.ª) o comisiones (2.ª)."""
        self.ensure_one()
        ver = self.version_id or self.employee_id.current_version_id
        wage_monthly = (ver.wage if ver else 0.0) or (self.employee_id.wage or 0.0)
        day_start = self.date_from.day if self.date_from else 1
        if day_start <= 15:
            return wage_monthly
        comm = self._l10n_hn_inputs_commission_amount(inputs)
        if not comm:
            comm = self._l10n_hn_commission_amount_from_result_rules(result_rules)
        if not comm and categories:
            comm = float(categories.get("COMISIONES", 0) or 0)
        return comm

    def _l10n_hn_compute_split_quincena_rap_period_fee(
        self, period_income, rap_settings, ihss_settings, version,
    ):
        """RAP quincenal: (ingreso del periodo - techo/2) × tasa (sin tope FOVIIF mensual)."""
        if period_income <= 0:
            return 0.0
        techo_half = self._l10n_hn_rap_techo_half_monthly(rap_settings, ihss_settings, version)
        rate = self._l10n_hn_rap_rate_pct(rap_settings, version)
        base = max(0.0, period_income - techo_half)
        return round(base * (rate / 100.0), 2)

    def _l10n_hn_compute_split_quincena_ihss_period_fee(self, period_income, ihss_settings):
        """IHSS quincenal al techo cuando el ingreso del periodo supera techo/15 días."""
        if period_income <= 0 or not ihss_settings:
            return 0.0
        ceiling_15_ivm = ihss_settings.get_ceiling_for_period(15, "ivm")
        if period_income >= ceiling_15_ivm:
            return ihss_settings.ihss_quota_biweekly
        taxable_ivm = min(period_income, ihss_settings.get_ceiling_for_period(15, "ivm"))
        taxable_em = min(period_income, ihss_settings.get_ceiling_for_period(15, "em"))
        return round(
            taxable_ivm * (ihss_settings.ivm_employee_rate / 100.0)
            + taxable_em * (ihss_settings.em_employee_rate / 100.0),
            2,
        )

    def _l10n_hn_compute_rap_employee_amount(self, categories, inputs, result_rules=None):
        """Retención RAP FOVIIF trabajador (negativa). MTD mensual si hay comisiones / ingreso variable."""
        self.ensure_one()
        employee = self.employee_id
        if not employee or employee.rap_excluded:
            return 0.0

        ver = self.version_id or employee.current_version_id
        rap_settings = self._l10n_hn_get_rap_settings()
        if not self._l10n_hn_rap_should_apply_this_period(rap_settings):
            return 0.0

        ihss_settings = self._l10n_hn_get_ihss_settings()
        if self._l10n_hn_use_split_quincena_payroll(categories, inputs):
            period_income = self._l10n_hn_split_quincena_rap_period_income(
                categories, inputs, result_rules,
            )
            cur = self._l10n_hn_compute_split_quincena_rap_period_fee(
                period_income, rap_settings, ihss_settings, ver,
            )
            return -cur if cur else 0.0

        if self._l10n_hn_use_biweekly_real_mtd_legal(categories, inputs):
            gross = self._l10n_hn_isr_gross_tax_base(categories)
            month_gross = self._l10n_hn_variable_legal_month_gross_mtd(gross)
            due_m = self._l10n_hn_compute_monthly_rap_employee_due(
                month_gross, rap_settings, ihss_settings, ver,
            )
            prior = self._l10n_hn_prior_slip_line_abs_total("RAP_FOVIIF_EMP")
            cur = round(max(0.0, due_m - prior), 2)
            return -cur if cur else 0.0

        if ver:
            if ver.rap_manual and ver.amount_rap_manual:
                return -round(abs(ver.amount_rap_manual), 2)
            if ver.rap_fee:
                return -round(abs(ver.rap_fee), 2)
            if ver.rap_foviif_amount_biweekly:
                return -round(abs(ver.rap_foviif_amount_biweekly), 2)
        return 0.0

    def _l10n_hn_compute_ihss_employee_amount(self, categories, inputs):
        """Retención IHSS trabajador (negativa)."""
        self.ensure_one()
        employee = self.employee_id
        if not employee or employee.ihss_excluded:
            return 0.0

        ver = self.version_id or employee.current_version_id
        if ver and ver.ihss_manual and ver.amount_ihss_manual:
            return -round(abs(ver.amount_ihss_manual), 2)

        ihss_settings = self._l10n_hn_get_ihss_settings()
        if not ihss_settings or not self._l10n_hn_ihss_should_apply_this_period(ihss_settings):
            return 0.0

        if self._l10n_hn_use_split_quincena_payroll(categories, inputs):
            period_income = self._l10n_hn_split_quincena_rap_period_income(
                categories, inputs,
            )
            cur = self._l10n_hn_compute_split_quincena_ihss_period_fee(
                period_income, ihss_settings,
            )
            return -cur if cur else 0.0

        if self._l10n_hn_use_biweekly_real_mtd_legal(categories, inputs):
            gross = self._l10n_hn_isr_gross_tax_base(categories)
            month_gross = self._l10n_hn_variable_legal_month_gross_mtd(gross)
            due_m = self._l10n_hn_compute_monthly_ihss_employee_due(month_gross, ihss_settings)
            prior = self._l10n_hn_prior_slip_line_abs_total("IHSS_EMP")
            cur = round(max(0.0, due_m - prior), 2)
            return -cur if cur else 0.0

        base = float(categories.get("BASIC", 0) or 0.0)
        ceiling_15 = ihss_settings.get_ceiling_for_period(15, "ivm")
        if base >= ceiling_15:
            return -round(ihss_settings.ihss_quota_biweekly, 2)
        taxable_ivm = min(base, ihss_settings.get_ceiling_for_period(15, "ivm"))
        taxable_em = min(base, ihss_settings.get_ceiling_for_period(15, "em"))
        amount = round(
            taxable_ivm * (ihss_settings.ivm_employee_rate / 100.0), 2
        ) + round(taxable_em * (ihss_settings.em_employee_rate / 100.0), 2)
        return -amount if amount else 0.0

    def _l10n_hn_regenerate_employee_payroll_summaries(self):
        """Actualiza historial salarial e ISR mensual del empleado."""
        self.ensure_one()
        if not self.employee_id or not self.date_to:
            return
        year, month = self.date_to.year, self.date_to.month
        self.env['l10n.hn.employee.monthly.salary.history'].regenerate_month(
            self.employee_id, year, month, company=self.company_id,
        )
        self.env['l10n.hn.employee.isr.monthly'].regenerate_month(
            self.employee_id, year, month, company=self.company_id,
        )

    def _l10n_hn_compute_isr_retention_amount(self, categories, result_rules, inputs):
        """Retención ISR para regla ISR (negativa)."""
        self.ensure_one()
        ihss_total = result_rules.get("IHSS_EMP", {}).get("total", 0)
        rap_total = result_rules.get("RAP_FOVIIF_EMP", {}).get("total", 0)
        IsrConfig = self.env["l10n.hn.isr.config"]
        if self._l10n_hn_use_split_quincena_payroll(categories, inputs):
            calc = IsrConfig.compute_withholding(
                self,
                categories=categories,
                inputs=inputs,
                ihss_employee=ihss_total,
                rap_employee=rap_total,
                use_split_quincena_isr=True,
                result_rules=result_rules,
            )
        elif self._l10n_hn_use_biweekly_real_mtd_legal(categories, inputs):
            calc = IsrConfig.compute_withholding(
                self,
                categories=categories,
                inputs=inputs,
                ihss_employee=ihss_total,
                rap_employee=rap_total,
                use_biweekly_monthly_mtd=True,
            )
        else:
            calc = IsrConfig.compute_withholding(self)
        return calc.get("period_amount", 0.0)
