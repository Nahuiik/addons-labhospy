# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SalaryAdvanceHn(models.Model):
    _inherit = "salary.advance"

    advance_target = fields.Selection(
        selection_add=[
            ("thirteenth", "Décimo tercer mes"),
            ("fourteenth", "Décimo cuarto mes"),
        ],
        ondelete={
            "thirteenth": "set default",
            "fourteenth": "set default",
        },
    )

    def _require_accounting_for_payment(self):
        self.ensure_one()
        if not self.journal_id or not self.debit_account_id or not self.credit_account_id:
            raise UserError(_(
                "Debe indicar el diario (banco o efectivo) y las cuentas contables del anticipo, "
                "o configurar los valores predeterminados en "
                "Ajustes → Nómina → Anticipos salariales (pestaña Honduras / nómina)."
            ))

    @api.model
    def _structure_type_for_advance_target(self, advance_target, employee):
        at = advance_target or "payroll"
        if at == "thirteenth":
            st = self.env.ref(
                "l10n_hn_hr_payroll.structure_type_13th_month", raise_if_not_found=False)
            if st:
                return st
        elif at == "fourteenth":
            st = self.env.ref(
                "l10n_hn_hr_payroll.structure_type_14th_month", raise_if_not_found=False)
            if st:
                return st
        return super()._structure_type_for_advance_target(advance_target, employee)

    @api.model
    def _supplement_pay_gross_and_periodicity(self, employee, advance_target, ref_date):
        if advance_target in ("thirteenth", "fourteenth") and employee and employee.current_version_id:
            limit_st = self._structure_type_for_advance_target(advance_target, employee)
            lim_per = self._periodicity_from_structure_type(limit_st)
            return (employee.current_version_id.wage or 0.0, lim_per)
        return super()._supplement_pay_gross_and_periodicity(employee, advance_target, ref_date)

    @api.model
    def _synthetic_payslip_for_limit(self, employee, period_start, period_end):
        ver = employee.current_version_id
        struct = ver.structure_type_id.default_struct_id if ver and ver.structure_type_id else False
        return self.env["hr.payslip"].new({
            "employee_id": employee.id,
            "company_id": employee.company_id.id,
            "date_from": period_start,
            "date_to": period_end,
            "struct_id": struct.id if struct else False,
        })

    @api.model
    def _rap_applies_on_reference_date(self, ver, ref_date, periodicity):
        if periodicity != "biweekly":
            return True
        rap_cfg = ver.rap_setup_id
        if not rap_cfg or not rap_cfg.include_in or rap_cfg.include_in == "both":
            return True
        is_first = ref_date.day <= 15
        if rap_cfg.include_in == "first":
            return is_first
        if rap_cfg.include_in == "second":
            return not is_first
        return True

    @api.model
    def _ihss_period_estimate(self, employee, ver, periodicity, ref_date):
        if employee.ihss_excluded:
            return 0.0
        if ver.ihss_manual and ver.amount_ihss_manual:
            return abs(ver.amount_ihss_manual)
        if periodicity in ("biweekly", "bi-weekly"):
            ihss_st = employee.ihss_settings_id
            if ihss_st:
                is_first = ref_date.day <= 15
                if is_first and not ihss_st.apply_first_quincena:
                    return 0.0
                if not is_first and not ihss_st.apply_second_quincena:
                    return 0.0
            return ver.ihss_amount_biweekly or 0.0
        if periodicity == "weekly":
            monthly = ver.ihss_amount_monthly or 0.0
            return round(monthly / 4.33, 2) if monthly else 0.0
        return ver.ihss_amount_monthly or 0.0

    @api.model
    def _rap_period_estimate(self, employee, ver, periodicity, ref_date):
        if employee.rap_excluded:
            return 0.0
        if not self._rap_applies_on_reference_date(ver, ref_date, periodicity):
            return 0.0
        if ver.rap_manual and ver.amount_rap_manual:
            return abs(ver.amount_rap_manual)
        if ver.rap_fee:
            return abs(ver.rap_fee)
        if periodicity in ("biweekly", "bi-weekly"):
            return ver.rap_foviif_amount_biweekly or 0.0
        if periodicity == "weekly":
            monthly = ver.rap_foviif_amount_monthly or 0.0
            return round(monthly / 4.33, 2) if monthly else 0.0
        return ver.rap_foviif_amount_monthly or 0.0

    @api.model
    def _isr_withholding_period_estimate(self, employee, ver):
        if employee.isr_excluded:
            return 0.0
        if ver.isr_manual and ver.amount_isr_manual:
            return abs(ver.amount_isr_manual)
        if ver.amount_isr_calculated:
            return abs(ver.amount_isr_calculated)
        payslip = self.env["hr.payslip"].search([
            ("employee_id", "=", employee.id),
            ("state", "=", "done"),
        ], order="date_to desc", limit=1)
        if payslip:
            isr_lines = payslip.line_ids.filtered(lambda l: l.code == "ISR")
            if isr_lines:
                return abs(isr_lines[0].total or 0.0)
        return 0.0

    @api.model
    def _is_payroll_isr_linked_deductions_estimate(self, employee, period_start, period_end):
        if not employee or employee.isr_excluded:
            return 0.0
        slip = self._synthetic_payslip_for_limit(employee, period_start, period_end)
        if not slip.date_from:
            return 0.0
        Ded = self.env["l10n.hn.isr.employee_deduction"]
        total = 0.0
        for code in ("afp_nomina", "colegio_profesional", "otros"):
            total += Ded.get_amount_by_type_for_payslip(slip, code)
        return total

    @api.model
    def _vecinal_from_last_payslip(self, employee):
        if not employee:
            return 0.0
        payslip = self.env["hr.payslip"].search([
            ("employee_id", "=", employee.id),
            ("state", "=", "done"),
        ], order="date_to desc", limit=1)
        if not payslip:
            return 0.0
        vec = payslip.line_ids.filtered(lambda l: l.code == "HN_VECINAL")
        if not vec:
            return 0.0
        return abs(vec[0].total or 0.0)

    @api.model
    def _legal_retentions_period_estimate(self, employee, ref_date=None, periodicity_for_limit=None):
        if not employee or not employee.current_version_id:
            return 0.0
        ref_date = ref_date or fields.Date.context_today(self)
        ref_date = fields.Date.to_date(ref_date)
        ver = employee.current_version_id
        periodicity = (
            periodicity_for_limit if periodicity_for_limit is not None else (ver.periodicity or "monthly")
        )
        period_start, period_end = self._payslip_period_bounds(ref_date, periodicity)
        ihss = self._ihss_period_estimate(employee, ver, periodicity, ref_date)
        rap = self._rap_period_estimate(employee, ver, periodicity, ref_date)
        isr = self._isr_withholding_period_estimate(employee, ver)
        linked = self._is_payroll_isr_linked_deductions_estimate(employee, period_start, period_end)
        vecinal = self._vecinal_from_last_payslip(employee)
        return ihss + rap + isr + linked + vecinal

    @api.model
    def _advance_reference_amount_and_note(self, employee, ref_date=None, advance_target="payroll"):
        if not employee or not employee.current_version_id:
            return 0.0, ""
        ref_date = ref_date or fields.Date.context_today(self)
        limit_st = self._structure_type_for_advance_target(advance_target, employee)
        contract_base = self._contract_period_net_estimate(employee, ref_date, advance_target)
        if not limit_st:
            return contract_base, _(
                "Neto estimado del período (bruto − recurrentes − IHSS/RAP/ISR y otras retenciones legales estimadas)"
            )
        if limit_st.advance_max_base != "last_payslip_net":
            return contract_base, _(
                "Bruto del período menos deducciones recurrentes y retenciones legales estimadas "
                "(según tipo de estructura del anticipo)"
            )
        net_amt = self._net_total_from_last_payslip_for_structure_type(employee, limit_st)
        if net_amt > 0:
            return net_amt, _("Neto de la última nómina de este tipo (línea NET)")
        if contract_base > 0:
            return contract_base, _("Sin recibo NET previo de este tipo; neto estimado del contrato")
        return 0.0, _("Sin dato de contrato ni nómina")

    @api.depends(
        "employee_id",
        "date",
        "advance_target",
        "employee_id.current_version_id",
        "employee_id.current_version_id.wage",
        "employee_id.current_version_id.schedule_pay",
        "employee_id.current_version_id.periodicity",
        "employee_id.current_version_id.structure_type_id",
        "employee_id.current_version_id.structure_type_id.max_advance_percentage",
        "employee_id.current_version_id.structure_type_id.advance_max_base",
        "employee_id.recurring_concept_ids",
        "employee_id.recurring_concept_ids.active",
        "employee_id.recurring_concept_ids.concept_type",
        "employee_id.recurring_concept_ids.amount",
        "employee_id.recurring_concept_ids.amount_type",
        "employee_id.recurring_concept_ids.is_loan",
        "employee_id.recurring_concept_ids.paid_installments",
        "employee_id.recurring_concept_ids.installments",
        "employee_id.recurring_concept_ids.apply_biweek",
        "employee_id.recurring_concept_ids.loan_split_quota_across_biweeks",
        "employee_id.recurring_concept_ids.loan_first_biweek_amount",
        "employee_id.recurring_concept_ids.date_start",
        "employee_id.recurring_concept_ids.company_id",
        "employee_id.rap_excluded",
        "employee_id.isr_excluded",
        "employee_id.ihss_settings_id",
        "employee_id.current_version_id.ihss_manual",
        "employee_id.current_version_id.amount_ihss_manual",
        "employee_id.current_version_id.ihss_amount_monthly",
        "employee_id.current_version_id.ihss_amount_biweekly",
        "employee_id.current_version_id.rap_manual",
        "employee_id.current_version_id.amount_rap_manual",
        "employee_id.current_version_id.rap_fee",
        "employee_id.current_version_id.rap_foviif_amount_monthly",
        "employee_id.current_version_id.rap_foviif_amount_biweekly",
        "employee_id.current_version_id.rap_setup_id",
        "employee_id.current_version_id.isr_manual",
        "employee_id.current_version_id.amount_isr_manual",
        "employee_id.current_version_id.amount_isr_calculated",
        "current_wage",
    )
    def _compute_max_advance(self):
        return super()._compute_max_advance()

    def _payslip_input_code(self):
        self.ensure_one()
        if self.advance_target == "thirteenth":
            return "ADV_13TH_MONTH"
        if self.advance_target == "fourteenth":
            return "ADV_14TH_MONTH"
        return super()._payslip_input_code()
