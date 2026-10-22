# -*- coding: utf-8 -*-

from odoo import fields, models


class ResBranch(models.Model):
    _inherit = "res.branch"

    transfer_sequence_id = fields.Many2one(
        "ir.sequence",
        string="Secuencia de Traslado",
        copy=False,
    )
    hn_remission_sequence_id = fields.Many2one(
        "ir.sequence",
        string="Secuencia guía de remisión (traslados)",
        copy=False,
        help=(
            "Si está definida, el número de guía de remisión de los traslados entre tiendas "
            "con origen en esta sucursal se toma de esta secuencia. Si no, se usa la secuencia global hn.remission."
        ),
    )
    pdf_watermark_branch_remission = fields.Binary(
        string="Plantilla PDF traslados (guía de remisión)",
        help=(
            "PDF o imagen usada como fondo (marca de agua) al imprimir la guía de remisión de "
            "traslados entre tiendas originados en esta sucursal. Solo se usa la primera página del PDF."
        ),
    )
    pdf_watermark_fname_branch_remission = fields.Char(
        string="Nombre archivo plantilla guía remisión",
    )
