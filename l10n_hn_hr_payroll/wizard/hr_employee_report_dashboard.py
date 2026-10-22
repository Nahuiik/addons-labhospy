# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import fields, models


class HrEmployeeReportDashboard(models.TransientModel):
    """Dashboard para acceder a los informes de empleados"""
    _name = 'hr.employee.report.dashboard'
    _description = 'Informes de Empleados'
    _rec_name = 'name'

    name = fields.Char(default='Dashboard de informes')
