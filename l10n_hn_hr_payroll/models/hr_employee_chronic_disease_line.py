# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik

from odoo import fields, models


class HrEmployeeChronicDiseaseLine(models.Model):
    """Detalle de enfermedad crónica (catálogo hr.disease, fechas y tratamiento)."""
    _name = "hr.employee.chronic.disease.line"
    _description = "Enfermedad crónica del empleado"
    _order = "disease_date desc, id"

    employee_id = fields.Many2one(
        "hr.employee",
        string="Empleado",
        required=True,
        ondelete="cascade",
        index=True,
    )
    disease_id = fields.Many2one(
        "hr.disease",
        string="Enfermedad",
        required=True,
        ondelete="restrict",
    )
    disease_date = fields.Date(string="Fecha")
    under_treatment = fields.Boolean(
        string="Tratamiento",
        default=False,
        help="Indica si el empleado está en tratamiento por esta enfermedad.",
    )
    treatment_place = fields.Char(
        string="Lugar de tratamiento",
        help="Centro, clínica u hospital donde recibe tratamiento.",
    )
