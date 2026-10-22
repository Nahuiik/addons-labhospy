# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models
from dateutil.relativedelta import relativedelta


class HrEmployeeFamily(models.Model):
    """Family members of employees"""
    _name = 'hr.employee.family'
    _description = 'Familiar del Empleado'
    _order = 'relation_id, name'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        ondelete='cascade',
        index=True
    )
    relation_id = fields.Many2one(
        'hr.family.relation',
        string='Parentesco',
        required=True
    )
    name = fields.Char(string='Nombre', required=True)
    birthdate = fields.Date(string='Fecha de Nacimiento')
    age = fields.Integer(
        string='Edad',
        compute='_compute_age',
        store=False
    )
    address = fields.Char(string='Domicilio')
    occupation = fields.Char(string='Ocupación')
    is_dependent = fields.Boolean(string='Dependiente', default=False)
    lives_with_employee = fields.Boolean(string='Vive con usted', default=False)
    works = fields.Boolean(string='Trabaja', default=False)

    @api.depends('birthdate')
    def _compute_age(self):
        today = fields.Date.today()
        for family in self:
            if family.birthdate:
                diff = relativedelta(today, family.birthdate)
                family.age = diff.years
            else:
                family.age = 0
