# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrEmployeeBeneficiary(models.Model):
    _name = 'hr.employee.beneficiary'
    _description = 'Beneficiario del empleado'
    _order = 'relation_id, name'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        ondelete='cascade',
        index=True,
    )
    relation_id = fields.Many2one(
        'hr.family.relation',
        string='Parentesco',
        required=True,
    )
    name = fields.Char(string='Nombre', required=True)
    percentage = fields.Float(string='Porcentaje', digits=(16, 2))

    @api.constrains('percentage')
    def _check_percentage(self):
        for line in self:
            if line.percentage < 0 or line.percentage > 100:
                raise ValidationError(_('El porcentaje debe estar entre 0 y 100.'))
