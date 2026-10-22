# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import fields, models


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    # Escalar para modifiers de vista OWL (evita .country_id.code sobre datos parciales).
    l10n_hn_leave_type_country_code = fields.Char(
        related='country_id.code',
        string='Código país (tipo ausencia)',
        readonly=True,
    )

    # Vistas antiguas en BD (Studio / módulos retirados) aún pueden referenciar este
    # campo; sin él falla la validación del árbol de vistas de hr.leave.type.
    hn_leave_category = fields.Char(
        string='Categoría ausencias (obsoleto)',
        help='Obsoleto: no usar. Se mantiene vacío para compatibilidad con vistas heredadas.',
    )

    is_ihss_incapacity = fields.Boolean(
        string='Incapacidad IHSS',
        default=False,
        help='Marcar para ausencias por incapacidad IHSS (Honduras). '
             'Días 1-3 calendario: patrono paga; día 4+: IHSS subsidio + complemento patrono.',
    )
