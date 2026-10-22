# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models
from dateutil.relativedelta import relativedelta


class HrLicenseType(models.Model):
    """Catalog of driver license types by country (multi-company)"""
    _name = 'hr.license.type'
    _description = 'Tipo de Licencia'
    _order = 'country_id, sequence, name'

    name = fields.Char(string='Código', required=True)
    description = fields.Char(string='Descripción', required=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(string='Activo', default=True)
    country_id = fields.Many2one(
        'res.country',
        string='País',
        required=True,
        default=lambda self: self.env.company.country_id,
        help='País al que aplica este tipo de licencia. Permite tener tipos por país en entornos multicompañía.'
    )

    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.name}: {record.description}"

    _name_uniq = models.Constraint(
        'unique (name, country_id)',
        'El código del tipo de licencia debe ser único por país.'
    )


class HrEmployeeLicense(models.Model):
    """Employee driver licenses"""
    _name = 'hr.employee.license'
    _description = 'Licencia de Empleado'
    _order = 'expiration_date'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        ondelete='cascade',
        index=True
    )
    license_type_id = fields.Many2one(
        'hr.license.type',
        string='Tipo de Licencia',
        required=True
    )
    license_number = fields.Char(string='Número de Licencia')
    expiration_date = fields.Date(string='Fecha de Vencimiento', required=True)
    time_to_expire = fields.Char(
        string='Tiempo para Vencer',
        compute='_compute_time_to_expire',
        store=False
    )
    is_expired = fields.Boolean(
        string='Vencida',
        compute='_compute_time_to_expire',
        store=False
    )

    @api.depends('expiration_date')
    def _compute_time_to_expire(self):
        today = fields.Date.today()
        for license in self:
            if license.expiration_date:
                if license.expiration_date < today:
                    license.is_expired = True
                    # Calculate how long ago it expired
                    diff = relativedelta(today, license.expiration_date)
                    parts = []
                    if diff.years:
                        parts.append(f"{diff.years} año(s)")
                    if diff.months:
                        parts.append(f"{diff.months} mes(es)")
                    if diff.days:
                        parts.append(f"{diff.days} día(s)")
                    license.time_to_expire = "Vencida hace " + ", ".join(parts) if parts else "Vencida hoy"
                else:
                    license.is_expired = False
                    diff = relativedelta(license.expiration_date, today)
                    parts = []
                    if diff.years:
                        parts.append(f"{diff.years} año(s)")
                    if diff.months:
                        parts.append(f"{diff.months} mes(es)")
                    if diff.days:
                        parts.append(f"{diff.days} día(s)")
                    license.time_to_expire = ", ".join(parts) if parts else "Vence hoy"
            else:
                license.time_to_expire = ""
                license.is_expired = False
