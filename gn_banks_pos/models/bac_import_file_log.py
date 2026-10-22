# -*- coding: utf-8 -*-

from odoo import fields, models


class BacPosImportFileLog(models.Model):
    """Registro por compañía del hash SHA-256 del CSV BAC ya importado."""

    _name = "bac.pos.import.file.log"
    _description = "Huella de importación CSV BAC POS"
    _order = "create_date desc"

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    file_hash = fields.Char(string="SHA-256", required=True, index=True)
    file_name = fields.Char(string="Nombre archivo (última importación)")
    history_id = fields.Many2one(
        "bac.pos.import.history",
        string="Historial de importación",
        ondelete="set null",
        index=True,
    )

    # Odoo 19: las restricciones SQL se declaran con models.Constraint.
    _file_hash_company_uniq = models.Constraint(
        "unique(company_id, file_hash)",
        "Este archivo CSV (mismo contenido) ya fue importado para esta compañía.",
    )
