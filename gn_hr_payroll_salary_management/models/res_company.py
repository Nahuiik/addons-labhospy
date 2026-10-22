# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    def _get_localization_trial_period_days(self):
        """Días de período de prueba según localización (HN/SV); módulos l10n extienden."""
        self.ensure_one()
        return 45

    salary_advance_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Diario anticipos salariales",
        check_company=True,
        domain="[('company_id', '=', id), ('type', 'in', ('bank', 'cash'))]",
        help="Diario de banco o efectivo con el que se registra el pago del anticipo al empleado.",
    )
    salary_advance_debit_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta débito anticipos salariales",
        check_company=True,
        domain="[('company_ids', 'parent_of', id)]",
        help="Cuenta de activo o anticipo a empleados (débito al pagar el anticipo).",
    )
    salary_advance_credit_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta crédito anticipos salariales",
        check_company=True,
        domain="[('company_ids', 'parent_of', id)]",
        help="Normalmente la cuenta del banco/caja asociada al diario (crédito al pagar el anticipo).",
    )
