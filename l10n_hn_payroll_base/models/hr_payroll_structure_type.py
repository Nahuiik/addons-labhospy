# -*- coding: utf-8 -*-
"""Extensión de tipos de estructura salarial para nómina CE (frecuencias, plantillas)."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayrollStructureType(models.Model):
    _inherit = "hr.payroll.structure.type"

    @api.model
    def _get_selection_schedule_pay(self):
        return [
            ("annually", "year"),
            ("semi-annually", "half-year"),
            ("quarterly", "quarter"),
            ("bi-monthly", "2 months"),
            ("monthly", "month"),
            ("semi-monthly", "half-month"),
            ("bi-weekly", "2 weeks"),
            ("weekly", "week"),
            ("daily", "day"),
        ]

    sequence = fields.Integer(default=10)
    default_schedule_pay = fields.Selection(
        selection=lambda self: self._get_selection_schedule_pay(),
        string="Scheduled Pay",
        default="monthly",
        help="Defines the frequency of the wage payment.",
    )
    struct_ids = fields.One2many("hr.payroll.structure", "type_id", string="Structures")
    default_struct_id = fields.Many2one("hr.payroll.structure", string="Pay Structure")
    default_work_entry_type_id = fields.Many2one(
        "hr.work.entry.type",
        string="Work Entry Type",
        help="Work entry type for regular attendances.",
        default=lambda self: self.env.ref(
            "hr_work_entry.work_entry_type_attendance", raise_if_not_found=False
        ),
    )
    wage_type = fields.Selection(
        [
            ("monthly", "Fixed Wage"),
            ("hourly", "Hourly Wage"),
        ],
        string="Wage Type",
        default="monthly",
        required=True,
    )
    struct_type_count = fields.Integer(compute="_compute_struct_type_count", string="Structure Type Count")

    def _compute_struct_type_count(self):
        for st in self:
            st.struct_type_count = len(st.struct_ids)

    def _check_country(self, vals):
        country_id = vals.get("country_id")
        if country_id and country_id not in self.env.companies.mapped("country_id").ids:
            raise UserError(
                _("You should also be logged into a company in %s to set this country.")
                % self.env["res.country"].browse(country_id).name
            )

    def write(self, vals):
        if self.env.context.get("payroll_check_country"):
            self._check_country(vals)
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("payroll_check_country"):
            for vals in vals_list:
                self._check_country(vals)
        return super().create(vals_list)
