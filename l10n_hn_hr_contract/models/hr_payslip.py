# © 2025 Grupo Nahuiik

from odoo import api, models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    @api.model
    def get_inputs(self, contracts, date_from, date_to):
        inputs = super().get_inputs(contracts, date_from, date_to)
        if not contracts:
            return inputs
        inputs_map = {(entry.get("contract_id"), entry.get("code")): entry for entry in inputs}
        for contract in contracts:
            benefit_lines = contract.benefit_line_ids.filtered(
                lambda line: line.include_in_payslip and line.periodicity == "monthly"
            )
            for benefit in benefit_lines:
                code = benefit.input_code or benefit.code
                key = (contract.id, code)
                amount = benefit._get_payslip_amount()
                if key in inputs_map:
                    inputs_map[key]["amount"] = amount
                else:
                    entry = {
                        "name": benefit.name,
                        "code": code,
                        "contract_id": contract.id,
                        "amount": amount,
                    }
                    inputs.append(entry)
                    inputs_map[key] = entry
        return inputs



