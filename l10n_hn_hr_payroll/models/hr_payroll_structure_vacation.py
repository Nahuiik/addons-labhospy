# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

from odoo import fields, models


class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    periodicity = fields.Selection(
        selection_add=[('yearly', 'Anual')],
        ondelete={'yearly': 'set default'},
    )

    hn_vacation_payroll_kind = fields.Selection(
        selection=[
            ('anniversary_month', 'Vacaciones HN — mes de aniversario'),
            ('year_end_december', 'Vacaciones HN — cierre diciembre'),
        ],
        string='Modalidad nómina vacaciones',
        help='Estructura solo para liquidar vacaciones Honduras en bruto (sin deducciones de la nómina normal). '
             'El importe usa los días acumulados en las asignaciones HN validadas menos lo ya liquidado en este '
             'tipo de nómina (campo “Días liquidados nómina vacaciones” en la asignación). '
             'Los días ya tomados y registrados como ausencia no reducen ese importe aquí: ese efecto debe reflejarse '
             'en la nómina regular. El saldo que ve el empleado para “tiempo libre” (asignación menos gozados menos '
             'liquidado nómina) puede diferir del importe pagado en esta liquidación.',
    )
