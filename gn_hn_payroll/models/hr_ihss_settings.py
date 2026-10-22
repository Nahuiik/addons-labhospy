# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrIhssSettings(models.Model):
    _name = "hr.ihss.settings"
    _description = "IHSS Settings"
    _order = "create_date desc"

    name = fields.Char(string="Nombre", required=True, default="IHSS")
    pay_periodicity = fields.Selection(
        [
            ("weekly", "Semanal"),
            ("bi-weekly", "Quincenal"),
            ("monthly", "Mensual"),
        ],
        string="Periodicidad Pago",
        default="monthly",
        required=True,
    )
    include_in = fields.Selection(
        [
            ("first", "Primera Quincena"),
            ("second", "Segunda Quincena"),
            ("both", "Ambas Quincenas"),
        ],
        string="Incluir En",
        default="first",
        required=True,
    )
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("validated", "Validado"),
        ],
        string="Estado",
        default="draft",
        required=True,
    )
    limit_enf_mat = fields.Float(string="Techo ENF-MAT", digits=(12, 2))
    limit_ivm = fields.Float(string="Techo IVM", digits=(12, 2))
    enf_mat_percentage = fields.Float(string="Porcentaje ENF-MAT (%)", digits=(12, 4))
    ivm_percentage = fields.Float(string="Porcentaje IVM (%)", digits=(12, 4))
    enf_mat_fee = fields.Float(
        string="Cuota ENF-MAT", compute="_compute_fees", store=True, digits=(12, 2)
    )
    ivm_fee = fields.Float(
        string="Cuota IVM", compute="_compute_fees", store=True, digits=(12, 2)
    )
    ihss_fee = fields.Float(
        string="Monto IHSS", compute="_compute_fees", store=True, digits=(12, 2)
    )
    bi_weekly_fee = fields.Float(
        string="Cuota Quincenal", compute="_compute_fees", store=True, digits=(12, 2)
    )

    def set_ihss(self):
        for rec in self:
            rec.state = "validated"

    def set_to_draft(self):
        self.write({"state": "draft"})

    @api.depends(
        "limit_enf_mat",
        "limit_ivm",
        "enf_mat_percentage",
        "ivm_percentage",
    )
    def _compute_fees(self):
        for rec in self:
            enf_mat_fee = (rec.limit_enf_mat or 0.0) * (rec.enf_mat_percentage or 0.0) / 100.0
            ivm_fee = (rec.limit_ivm or 0.0) * (rec.ivm_percentage or 0.0) / 100.0
            ihss_fee = enf_mat_fee + ivm_fee
            rec.enf_mat_fee = enf_mat_fee
            rec.ivm_fee = ivm_fee
            rec.ihss_fee = ihss_fee
            rec.bi_weekly_fee = ihss_fee / 2.0
