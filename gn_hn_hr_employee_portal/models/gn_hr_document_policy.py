# -*- coding: utf-8 -*-
from odoo import fields, models


class GnHrDocumentPolicy(models.Model):
    _name = 'gn.hr.document.policy'
    _description = 'Política o documento a aceptar por empleados'

    name = fields.Char(string='Nombre', required=True)
    content = fields.Html(string='Contenido')
    version = fields.Char(string='Versión')
    active = fields.Boolean(default=True)
    required_for_portal = fields.Boolean(
        string='Requerida para portal',
        default=False,
        help='Si está activo, el empleado debe aceptar antes de usar el portal.',
    )
    sequence = fields.Integer(default=10)
