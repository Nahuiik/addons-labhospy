# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    hr_contract_work_days_per_year = fields.Float(
        string="Días laborales por año",
        help="Número de días laborales utilizados para calcular el sacrificio salarial.",
        default=261.0,
    )
    hr_contract_timeoff_auto_allocation = fields.Boolean(
        string="Asignar vacaciones automáticas",
        help="Cuando se active, el botón del contrato creará automáticamente una asignación de vacaciones.",
    )
    hr_contract_timeoff_auto_allocation_type_id = fields.Many2one(
        "hr.leave.type",
        string="Tipo de vacaciones",
        domain="[('requires_allocation', '=', True)]",
    )

    @api.constrains('hr_contract_timeoff_auto_allocation', 'hr_contract_timeoff_auto_allocation_type_id')
    def _check_auto_allocation_type(self):
        for company in self:
            if company.hr_contract_timeoff_auto_allocation and not company.hr_contract_timeoff_auto_allocation_type_id:
                raise ValidationError(_("Debe definir un tipo de vacaciones cuando activa la asignación automática."))



