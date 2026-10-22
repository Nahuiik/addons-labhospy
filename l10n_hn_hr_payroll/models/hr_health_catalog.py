# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import fields, models


class HrSport(models.Model):
    """Catalog of sports"""
    _name = 'hr.sport'
    _description = 'Deporte'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    active = fields.Boolean(string='Activo', default=True)

    _name_uniq = models.Constraint(
        'unique (name)',
        'El nombre del deporte debe ser único.'
    )


class HrHobby(models.Model):
    """Catalog of hobbies"""
    _name = 'hr.hobby'
    _description = 'Pasatiempo'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    active = fields.Boolean(string='Activo', default=True)

    _name_uniq = models.Constraint(
        'unique (name)',
        'El nombre del pasatiempo debe ser único.'
    )


class HrAllergy(models.Model):
    """Catálogo de alergias (salud)"""
    _name = 'hr.allergy'
    _description = 'Alergia'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True, translate=True)
    active = fields.Boolean(string='Activo', default=True)

    _name_uniq = models.Constraint(
        'unique (name)',
        'El nombre de la alergia debe ser único.'
    )


class HrDisease(models.Model):
    """Catalog of diseases"""
    _name = 'hr.disease'
    _description = 'Enfermedad'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    active = fields.Boolean(string='Activo', default=True)

    _name_uniq = models.Constraint(
        'unique (name)',
        'El nombre de la enfermedad debe ser único.'
    )


class HrMedication(models.Model):
    """Catalog of medications"""
    _name = 'hr.medication'
    _description = 'Medicamento'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    active = fields.Boolean(string='Activo', default=True)

    _name_uniq = models.Constraint(
        'unique (name)',
        'El nombre del medicamento debe ser único.'
    )


class HrSurgery(models.Model):
    """Catalog of surgeries"""
    _name = 'hr.surgery'
    _description = 'Cirugía'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    active = fields.Boolean(string='Activo', default=True)

    _name_uniq = models.Constraint(
        'unique (name)',
        'El nombre de la cirugía debe ser único.'
    )
