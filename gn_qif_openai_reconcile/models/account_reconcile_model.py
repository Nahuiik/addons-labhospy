# -*- coding: utf-8 -*-
"""Extensión Nahuiik sobre modelos estándar `account.reconcile.model` (CE)."""

from odoo import fields, models


class AccountReconcileModel(models.Model):
    _inherit = 'account.reconcile.model'

    gn_creation_source = fields.Selection(
        selection=[
            ('standard', 'Usuario / Odoo estándar'),
            ('wizard_template', 'Plantilla Nahuiik (asistente)'),
            ('ai_promoted', 'IA (promoción desde patrones)'),
            ('import_linked', 'Vínculo importación Nahuiik'),
        ],
        string='Origen Nahuiik',
        default='standard',
        copy=False,
        help='Trazabilidad opcional entre modelos creados en Odoo estándar y utilidades Nahuiik (plantillas e IA).',
    )
    gn_file_format_key = fields.Char(
        string='Formato extracto Nahuiik',
        help='Misma convención que gn.qif.reconcile.learn.file_format_key cuando aplique.',
    )

    gn_qif_learn_ids = fields.One2many(
        comodel_name='gn.qif.reconcile.learn',
        inverse_name='reconcile_model_id',
        string='Patrones IA relacionados',
    )
