# -*- coding: utf-8 -*-
from odoo import fields, models


class L10nHnConsumeReasonType(models.Model):
    _name = "l10n_hn.consume.reason.type"
    _description = "Tipo de motivo de consumo"
    _order = "sequence, name, id"

    name = fields.Char(string="Motivo", required=True, translate=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    consume_account_id = fields.Many2one(
        "account.account",
        string="Cuenta contable (consumo)",
        check_company=True,
        domain=(
            "[('company_ids', 'parent_of', company_id), "
            "('company_ids', 'child_of', company_id)]"
        ),
        help="Cuenta aplicada en cada línea del documento de consumo al seleccionar este motivo.",
    )

    _name_company_uniq = models.Constraint(
        "unique (name, company_id)",
        "Ya existe un tipo de motivo con ese nombre en esta compañía.",
    )
