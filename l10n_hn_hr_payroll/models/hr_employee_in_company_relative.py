# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrEmployeeInCompanyRelative(models.Model):
    """Parientes del empleado que también trabajan en la empresa (con parentesco)."""
    _name = 'hr.employee.in.company.relative'
    _description = 'Pariente en la empresa'
    _order = 'id'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Titular',
        required=True,
        ondelete='cascade',
        index=True,
    )
    colleague_id = fields.Many2one(
        'hr.employee',
        string='Pariente (empleado)',
        required=True,
        ondelete='cascade',
        check_company=True,
    )
    relation_id = fields.Many2one(
        'hr.family.relation',
        string='Parentesco',
        required=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='employee_id.company_id',
        store=True,
        readonly=True,
    )

    _employee_colleague_uniq = models.Constraint(
        'unique(employee_id, colleague_id)',
        'No puede repetir el mismo empleado en la lista de parientes.',
    )

    @api.constrains('employee_id', 'colleague_id')
    def _check_not_self(self):
        for line in self:
            if line.employee_id == line.colleague_id:
                raise ValidationError(
                    _('No puede indicarse a sí mismo como pariente en la empresa.')
                )
