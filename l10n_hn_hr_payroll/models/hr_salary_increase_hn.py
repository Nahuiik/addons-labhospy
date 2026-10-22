# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _


class HrSalaryIncreaseHn(models.Model):
    _inherit = "hr.salary.increase"

    effective_period_id = fields.Many2one(
        "l10n.hn.payroll.period",
        string="Quincena efectiva",
        compute="_compute_effective_period",
        store=True,
        help="Quincena en la que el aumento se reflejará en el recibo de nómina.",
    )
    effective_period_warning = fields.Char(
        string="Aviso quincena",
        compute="_compute_effective_period",
        store=True,
    )

    @api.depends("date", "company_id")
    def _compute_effective_period(self):
        for rec in self:
            if not rec.date:
                rec.effective_period_id = False
                rec.effective_period_warning = ""
                continue
            period = rec.env["l10n.hn.payroll.period"].search([
                ("date_start", "<=", rec.date),
                ("date_end", ">=", rec.date),
                ("company_id", "=", rec.company_id.id),
            ], limit=1)
            rec.effective_period_id = period
            if period:
                rec.effective_period_warning = _(
                    "El aumento se verá reflejado en el recibo de nómina de la quincena: %s"
                ) % period.name
            else:
                rec.effective_period_warning = _(
                    "No se encontró una quincena configurada para la fecha efectiva. "
                    "Verifique que exista el período en Nómina → Quincenas."
                )
