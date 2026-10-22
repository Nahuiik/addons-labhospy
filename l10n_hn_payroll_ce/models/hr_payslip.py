# © 2025 Grupo Nahuiik

from odoo import api, fields, models
from odoo.fields import Command


class HrPayslipInput(models.Model):
    _inherit = "hr.payslip.input"

    employee_input_id = fields.Many2one(
        "hr.employee.salary.input",
        string="Employee salary input",
    )


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    @api.depends(
        "date_from",
        "date_to",
        "employee_id",
        "contract_id",
        "struct_id",
        "employee_id.salary_input_ids",
        "employee_id.salary_input_ids.amount",
        "employee_id.salary_input_ids.sequence",
        "employee_id.salary_input_ids.date_start",
        "employee_id.salary_input_ids.date_end",
        "employee_id.salary_input_ids.struct_ids",
        "employee_id.salary_input_ids.active",
    )
    def _compute_input_line_ids(self):
        super()._compute_input_line_ids()
        for slip in self:
            slip._sync_employee_salary_inputs()

    def _sync_employee_salary_inputs(self):
        self.ensure_one()
        employee = self.employee_id
        if not employee:
            self._remove_employee_salary_input_lines()
            return
        valid_inputs = employee.salary_input_ids.filtered(lambda rec: rec.active)
        if not valid_inputs:
            self._remove_employee_salary_input_lines()
            return

        struct = self.struct_id
        if not struct:
            self._remove_employee_salary_input_lines()
            return

        allowed_input_types = struct.input_line_type_ids
        valid_inputs = valid_inputs.filtered(
            lambda rec: rec.input_type_id in allowed_input_types
            and (not rec.struct_ids or struct in rec.struct_ids)
            and self._is_salary_input_within_dates(rec)
        )

        commands = []
        linked_lines = self.input_line_ids.filtered(lambda line: line.employee_input_id)
        to_unlink = linked_lines.filtered(lambda line: line.employee_input_id not in valid_inputs)
        if to_unlink:
            commands.extend(Command.unlink(line.id) for line in to_unlink)
            linked_lines -= to_unlink

        contract = self.contract_id or employee.version_id
        if not contract:
            self._remove_employee_salary_input_lines()
            return

        for employee_input in valid_inputs:
            name = employee_input.name or employee_input.input_type_id.name
            existing_lines = linked_lines.filtered(lambda line: line.employee_input_id == employee_input)
            should_apply, amount = employee_input._get_amount_for_payslip(self)
            if not should_apply:
                if existing_lines:
                    commands.extend(Command.unlink(line.id) for line in existing_lines)
                    linked_lines -= existing_lines
                continue

            if self.credit_note:
                amount = -amount

            if existing_lines:
                primary_line = existing_lines[0]
                duplicate_lines = existing_lines - primary_line
                if duplicate_lines:
                    commands.extend(Command.unlink(line.id) for line in duplicate_lines)
                    linked_lines -= duplicate_lines
                values = {
                    "name": name,
                    "amount": amount,
                    "input_type_id": employee_input.input_type_id.id,
                    "sequence": employee_input.sequence,
                }
                if (
                    primary_line.name != values["name"]
                    or primary_line.amount != values["amount"]
                    or primary_line.input_type_id.id != values["input_type_id"]
                    or primary_line.sequence != values["sequence"]
                    or primary_line.contract_id.id != contract.id
                ):
                    values["contract_id"] = contract.id
                    commands.append(Command.update(primary_line.id, values))
            else:
                commands.append(
                    Command.create(
                        {
                            "name": name,
                            "amount": amount,
                            "input_type_id": employee_input.input_type_id.id,
                            "sequence": employee_input.sequence,
                            "employee_input_id": employee_input.id,
                            "contract_id": contract.id,
                        }
                    )
                )

        if commands:
            self.update({"input_line_ids": commands})

    def _is_salary_input_within_dates(self, employee_input):
        self.ensure_one()
        if employee_input.date_start and employee_input.date_start > self.date_to:
            return False
        if employee_input.date_end and employee_input.date_end < self.date_from:
            return False
        return True

    def _remove_employee_salary_input_lines(self):
        self.ensure_one()
        linked_lines = self.input_line_ids.filtered(lambda line: line.employee_input_id)
        if linked_lines:
            self.update(
                {
                    "input_line_ids": [
                        Command.unlink(line.id) for line in linked_lines
                    ]
                }
            )

    def _get_ihss_period_bucket(self):
        self.ensure_one()
        if not self.date_from or not self.date_to:
            return "full"
        start = self.date_from
        end = self.date_to
        if start.year == end.year and start.month == end.month:
            if end.day <= 15:
                return "first_half"
            if start.day > 15:
                return "second_half"
        return "full"
