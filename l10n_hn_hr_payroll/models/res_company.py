# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    hn_default_vacation_plan_id = fields.Many2one(
        'gn.hn.vacation.plan',
        string='Plan de vacaciones por defecto',
        help='Plan asignado a empleados que no tienen uno definido',
        domain=lambda self: [('company_id', 'in', [self.id, False])],
    )
    hr_payroll_manager_id = fields.Many2one(
        comodel_name='res.users',
        string='Encargado RRHH',
        domain=[('active', '=', True)],
        help='Usuario responsable del área de Recursos Humanos.',
    )
    hr_payroll_approver_id = fields.Many2one(
        comodel_name='res.users',
        string='Aprobador de Nómina',
        domain=[('active', '=', True)],
        help='Usuario que aprueba las nóminas.',
    )
    hr_payroll_reviewer_id = fields.Many2one(
        comodel_name='res.users',
        string='Revisor de Nómina',
        domain=[('active', '=', True)],
        help='Usuario que revisa las nóminas.',
    )
    payroll_auditor_ids = fields.Many2many(
        comodel_name='res.users',
        relation='res_company_payroll_auditor_rel',
        column1='company_id',
        column2='user_id',
        string='Auditores de Nómina',
        domain=[('active', '=', True)],
        help='Usuarios que reciben las auditorías pendientes de nómina.',
    )
    l10n_hn_trial_period_days = fields.Integer(
        string='Días de Período de Prueba (Honduras)',
        default=45,
        help='Cantidad de días calendario del período de prueba para nuevos empleados (compañías Honduras).',
    )
    l10n_hn_hr_alert_recipient_ids = fields.Many2many(
        comodel_name='res.users',
        relation='res_company_hr_alert_recipient_rel',
        column1='company_id',
        column2='user_id',
        string='Receptores de Alertas RRHH (HN)',
        domain=[('active', '=', True)],
        help='Usuarios que reciben alertas de RRHH (período de prueba, etc.) en compañías Honduras.',
    )

    def _get_localization_trial_period_days(self):
        self.ensure_one()
        if self.country_id.code == 'HN':
            return self.l10n_hn_trial_period_days or 45
        return super()._get_localization_trial_period_days()
    is_microenterprise = fields.Boolean(
        string='Microempresa (Art. 120-A)',
        help='Topes de cesantía 15 meses; no aplica literal g) Art. 120.',
    )

    @api.constrains('hn_default_vacation_plan_id')
    def _check_hn_default_vacation_plan_company(self):
        for company in self:
            plan = company.hn_default_vacation_plan_id
            if plan and plan.company_id and plan.company_id != company:
                raise ValidationError(
                    'El plan de vacaciones por defecto debe pertenecer a esta compañía o ser compartido (sin compañía).'
                )