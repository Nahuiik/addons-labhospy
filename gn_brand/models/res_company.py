# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    systray_name = fields.Char(
        string='Nombre Systray',
        help='Texto personalizado que se mostrará en el systray (barra superior) en lugar del nombre de la empresa'
    )


