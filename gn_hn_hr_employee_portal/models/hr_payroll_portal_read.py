# -*- coding: utf-8 -*-
# Permite a usuarios portal leer datos mínimos de contrato/nómina para límites de anticipo
# sin otorgar el grupo hr_payroll completo (los campos en enterprise están acotados a payroll user).
from odoo import fields, models

_G_PAYROLL = 'hr_payroll.group_hr_payroll_user'
_G_PORTAL = 'gn_hn_hr_employee_portal.group_employee_portal_user'
_GROUPS_PAYROLL_AND_PORTAL = '%s,%s' % (_G_PAYROLL, _G_PORTAL)


class HrVersionPortalRead(models.Model):
    _inherit = 'hr.version'

    structure_type_id = fields.Many2one(groups=_GROUPS_PAYROLL_AND_PORTAL)
    wage = fields.Monetary(groups=_GROUPS_PAYROLL_AND_PORTAL)


class HrEmployeePortalPayrollRead(models.Model):
    _inherit = 'hr.employee'

    wage = fields.Monetary(
        readonly=False,
        related='version_id.wage',
        inherited=True,
        groups=_GROUPS_PAYROLL_AND_PORTAL,
    )
    structure_type_id = fields.Many2one(
        related='version_id.structure_type_id',
        inherited=True,
        store=True,
        groups=_GROUPS_PAYROLL_AND_PORTAL,
    )
