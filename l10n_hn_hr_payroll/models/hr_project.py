# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import fields, models


class HrProject(models.Model):
    """Catálogo de proyectos para empleados"""
    _name = 'hr.project'
    _description = 'Proyecto'
    _order = 'sequence, name'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    name = fields.Char(string='Nombre', required=True)
    code = fields.Char(string='Código', size=32)
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(string='Activo', default=True)
