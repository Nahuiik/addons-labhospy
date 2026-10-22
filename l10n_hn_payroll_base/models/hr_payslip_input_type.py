# -*- coding: utf-8 -*-
"""
Tipos de entrada de recibo (nómina CE).

Implementación original: modela el contrato funcional público (mismo _name y campos
esperados por datos locales) sin depender de módulos de nómina propietarios.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayslipInputType(models.Model):
    _name = "hr.payslip.input.type"
    _description = "Payslip Input Type"

    name = fields.Char(string="Description", required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Stable code used in salary rules (e.g. inputs dictionary in python code).",
    )
    struct_ids = fields.Many2many(
        "hr.payroll.structure",
        "hr_payroll_structure_hr_payslip_input_type_rel",
        "input_type_id",
        "structure_id",
        string="Linked structures",
        help="Salary structures that list this input; the inverse field on the structure selects inputs for payslips.",
    )
    country_id = fields.Many2one(
        "res.country",
        string="Country",
        default=lambda self: self.env.company.country_id,
    )
    country_code = fields.Char(related="country_id.code")
    active = fields.Boolean(default=True)
    available_in_attachments = fields.Boolean(
        string="Available in salary adjustments",
        help="When enabled, this type may be chosen on salary adjustment records.",
    )
    is_quantity = fields.Boolean(
        string="Is quantity",
        help="If set, user-entered values represent a count rather than money.",
    )
    default_no_end_date = fields.Boolean(string="No end date by default")

    @api.ondelete(at_uninstall=False)
    def _unlink_except_module_records(self):
        xml_map = self.get_external_id()
        for rec in self:
            xid = xml_map.get(rec.id)
            if xid and not xid.startswith("__export__"):
                raise UserError(
                    _("This input type is shipped as data; archive it instead of deleting.")
                )
