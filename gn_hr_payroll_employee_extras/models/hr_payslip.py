# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik

import json

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    gn_quota_registration_json = fields.Text(
        string="Registro cuotas (técnico)",
        copy=False,
        groups="l10n_hn_payroll_base.group_hn_payroll_user",
    )

    def action_payslip_done(self):
        res = super().action_payslip_done()
        self._gn_register_recurring_quotas_on_validate()
        return res

    def action_payslip_draft(self):
        self._gn_revert_recurring_quotas_on_unvalidate()
        return super().action_payslip_draft()

    def action_payslip_cancel(self):
        to_revert = self.filtered(lambda slip: slip.state in ("validated", "paid", "done"))
        to_revert._gn_revert_recurring_quotas_on_unvalidate()
        return super().action_payslip_cancel()

    def _gn_should_count_loan_installment(self, concept):
        """Cuota partida entre quincenas: solo cuenta al cerrar la 2.ª quincena."""
        self.ensure_one()
        if not (
            concept.is_loan
            and concept.loan_split_quota_across_biweeks
            and concept.apply_biweek == "both"
            and concept._gn_employee_version_is_biweekly(self.employee_id)
        ):
            return True
        if not self.date_from:
            return True
        return self.date_from.day >= 16

    def _gn_register_recurring_quotas_on_validate(self):
        Concept = self.env["hr.employee.recurring.concept"]
        Input = self.env["hr.payslip.input"]
        has_employee_input = "employee_input_id" in Input._fields

        for slip in self:
            if slip.gn_quota_registration_json:
                continue

            rows = []
            for line in slip.input_line_ids:
                if not line.amount:
                    continue

                concept = line.recurring_concept_id
                if concept and concept.is_loan:
                    if not slip._gn_should_count_loan_installment(concept):
                        continue
                    if concept.paid_installments >= concept._gn_loan_total_payment_count():
                        continue
                    concept.manual_paid_installments += 1
                    total_payments = concept._gn_loan_total_payment_count()
                    finished = concept.paid_installments >= total_payments
                    if finished:
                        concept.active = False
                    concept.message_post(
                        body=_(
                            "Cuota %(paid)d/%(total)d registrada al validar el recibo %(slip)s.",
                            paid=concept.paid_installments,
                            total=total_payments,
                            slip=slip.display_name,
                        )
                    )
                    rows.append(
                        {
                            "kind": "loan",
                            "concept_id": concept.id,
                            "delta": 1,
                            "reactivate": finished,
                        }
                    )
                    continue

                if has_employee_input and line.employee_input_id:
                    emp_input = line.employee_input_id
                    if emp_input.periodicity != "finite":
                        continue
                    remaining = emp_input.payments_remaining or 0
                    if remaining <= 0:
                        continue
                    emp_input.payments_remaining = remaining - 1
                    rows.append(
                        {
                            "kind": "salary_input",
                            "employee_input_id": emp_input.id,
                            "delta": 1,
                        }
                    )

            if rows:
                slip.gn_quota_registration_json = json.dumps(rows)

    def _gn_revert_recurring_quotas_on_unvalidate(self):
        Concept = self.env["hr.employee.recurring.concept"]
        SalaryInput = self.env.get("hr.employee.salary.input")

        for slip in self:
            data = slip.gn_quota_registration_json
            if not data:
                continue
            try:
                rows = json.loads(data)
            except json.JSONDecodeError:
                slip.gn_quota_registration_json = False
                continue

            for row in rows:
                kind = row.get("kind")
                delta = row.get("delta", 1)
                if kind == "loan":
                    concept = Concept.browse(row.get("concept_id"))
                    if not concept.exists():
                        continue
                    concept.manual_paid_installments = max(
                        0, concept.manual_paid_installments - delta
                    )
                    if row.get("reactivate") and concept.is_loan:
                        concept.active = True
                    concept.message_post(
                        body=_(
                            "Cuota revertida al pasar el recibo %(slip)s a borrador o cancelado.",
                            slip=slip.display_name,
                        )
                    )
                elif kind == "salary_input" and SalaryInput is not None:
                    emp_input = SalaryInput.browse(row.get("employee_input_id"))
                    if emp_input.exists():
                        emp_input.payments_remaining = (
                            emp_input.payments_remaining or 0
                        ) + delta

            slip.gn_quota_registration_json = False

    def _check_send_payslip_mail(self):
        """Respeta la preferencia del lote (pay run) sobre envío de correo al validar."""
        if not super()._check_send_payslip_mail():
            return False
        run = self.payslip_run_id
        if run and "send_payslip_email_on_validate" in run._fields:
            return bool(run.send_payslip_email_on_validate)
        return True

    def action_print_payslip(self):
        """Enterprise devuelve act_url (/print/payslips): el PDF va por HTTP y no pasan los
        manejadores de ir.actions.report (p. ej. modal Imprimir/Descargar/Abrir).

        Cuando todos los recibos usan el mismo informe PDF, ejecutamos ese informe desde el cliente.
        Si hay varios informes distintos, se conserva la fusión servidor de Odoo EE.
        """
        if self.filtered("error_count"):
            raise ValidationError(self._get_error_message())
        mapped = self._get_pdf_reports()
        if len(mapped) != 1:
            return super().action_print_payslip()
        report = next(iter(mapped.keys()))
        payslips = next(iter(mapped.values()))
        if not report:
            return super().action_print_payslip()
        return report.report_action(payslips.ids)

    def action_send_payslip_by_email(self):
        """Envío manual con plantilla estándar (no aplica el toggle del lote)."""
        for payslip in self:
            payslip._gn_send_payslip_email_manual_single()
        if len(self) == 1:
            msg = _("Se envió el recibo por correo al empleado.")
        else:
            msg = _("Se enviaron %(count)d recibos por correo.", count=len(self))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Correo"),
                "message": msg,
                "type": "success",
                "sticky": False,
            },
        }

    def _gn_send_payslip_email_manual_single(self):
        self.ensure_one()
        if self.state == "cancel":
            raise UserError(_("No se puede enviar por correo un recibo cancelado."))
        if not self.line_ids:
            raise UserError(_("Calcule la hoja antes de enviar el recibo por correo."))
        employee = self.employee_id
        if not employee:
            raise UserError(_("El recibo no tiene empleado."))
        partner = employee.work_contact_id
        if not partner:
            raise UserError(_("El empleado no tiene contacto laboral configurado."))
        if not partner.email:
            raise UserError(_("El empleado no tiene correo electrónico."))
        self._gn_ensure_payslip_pdf_attachment()
        template = self._get_email_template()
        if not template:
            raise UserError(_("No hay plantilla de correo para nuevos recibos de nómina."))
        template.send_mail(self.id, email_layout_xmlid="mail.mail_notification_light")

    def _gn_ensure_payslip_pdf_attachment(self):
        """Genera el PDF del recibo como adjunto vinculado (misma lógica que al validar)."""
        self.ensure_one()
        mapped_reports = self._get_pdf_reports()
        generic_name = _("Recibo de nómina")
        attachments_vals_list = []
        report_engine = self.env["ir.actions.report"].sudo()
        lang = self.employee_id.lang or self.env.lang
        for report, payslips in mapped_reports.items():
            if self not in payslips:
                continue
            pdf_content, _dummy = report_engine.with_context(lang=lang)._render_qweb_pdf(
                report, self.id
            )
            if report.print_report_name:
                pdf_name = safe_eval(report.print_report_name, {"object": self})
            else:
                pdf_name = generic_name
            attachments_vals_list.append(
                {
                    "name": pdf_name,
                    "type": "binary",
                    "raw": pdf_content,
                    "res_model": self._name,
                    "res_id": self.id,
                }
            )
        if attachments_vals_list:
            self.env["ir.attachment"].sudo().create(attachments_vals_list)

    def _get_or_create_input_type(self, code, name):
        self.ensure_one()
        input_type = self.env["hr.payslip.input.type"].search(
            [("code", "=", code)],
            limit=1,
        )
        if not input_type:
            input_type = self.env["hr.payslip.input.type"].create(
                {"code": code, "name": name}
            )
        return input_type

    def _calculate_concept_amount(self, concept):
        self.ensure_one()
        if concept.amount_type == "fixed":
            return concept.amount
        if concept.amount_type == "percentage":
            if self.line_ids:
                basic_line = self.line_ids.filtered(lambda l: l.code == "BASIC")
                if basic_line:
                    basic_amount = basic_line[0].total
                    return (basic_amount * concept.amount) / 100.0

            version_sudo = (
                self.employee_id.current_version_id.sudo()
                if self.employee_id.current_version_id
                else False
            )
            if version_sudo:
                wage = version_sudo.wage or 0.0
                periodicity = version_sudo.periodicity or "monthly"

                if periodicity == "biweekly":
                    period_wage = wage / 2.0
                elif periodicity == "weekly":
                    period_wage = wage / 4.33
                else:
                    period_wage = wage

                return (period_wage * concept.amount) / 100.0
            if self.employee_id.wage:
                return (self.employee_id.wage * concept.amount) / 100.0

        return 0.0

    def _gn_sync_recurring_concepts_inputs(self):
        """Sincroniza conceptos recurrentes del empleado como entradas del recibo."""
        self.ensure_one()
        if not self.employee_id or not self.date_from or not self.date_to:
            return

        concepts = self.env["hr.employee.recurring.concept"].search(
            [
                ("employee_id", "=", self.employee_id.id),
                ("active", "=", True),
                ("company_id", "=", self.company_id.id),
            ]
        )

        valid_concepts = []
        for concept in concepts:
            if concept.employee_id.id != self.employee_id.id:
                continue
            if concept.date_start and concept.date_start > self.date_to:
                continue
            if concept.date_end and concept.date_end < self.date_from:
                continue
            if concept.is_loan:
                if concept._gn_loan_is_complete():
                    continue
            if concept.apply_biweek and concept.apply_biweek != "both":
                version_sudo = (
                    self.employee_id.current_version_id.sudo()
                    if self.employee_id.current_version_id
                    else False
                )
                periodicity = version_sudo.periodicity if version_sudo else "monthly"
                if periodicity == "biweekly":
                    date_from_day = self.date_from.day
                    is_first_biweek = date_from_day <= 15
                    is_second_biweek = date_from_day >= 16
                    if concept.apply_biweek == "first" and not is_first_biweek:
                        continue
                    if concept.apply_biweek == "second" and not is_second_biweek:
                        continue

            valid_concepts.append(concept)

        for concept in valid_concepts:
            if concept.code:
                input_code = concept.code
            else:
                input_code = concept.name.upper().replace(" ", "_").replace("-", "_")[
                    :20
                ]

            input_type = self._get_or_create_input_type(input_code, concept.name)
            if not input_type:
                continue

            amount = concept._gn_apply_loan_biweek_split_to_amount(
                concept._gn_effective_recurring_deduction_base(
                    self._calculate_concept_amount(concept)
                ),
                self.employee_id,
                self.date_from,
            )
            if amount == 0:
                continue

            existing_input = self.input_line_ids.filtered(
                lambda line: line.input_type_id.code == input_code
            )

            if existing_input:
                existing_input[0].write(
                    {"amount": amount, "recurring_concept_id": concept.id}
                )
            else:
                self.with_context(_skip_recurring_sync=True).write(
                    {
                        "input_line_ids": [
                            (
                                0,
                                0,
                                {
                                    "name": concept.name,
                                    "input_type_id": input_type.id,
                                    "amount": amount,
                                    "recurring_concept_id": concept.id,
                                },
                            )
                        ]
                    }
                )
