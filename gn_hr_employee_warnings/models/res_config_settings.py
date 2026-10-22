# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    gn_hr_contract_expiration_warning_days = fields.Integer(
        string="Días antes de vencimiento de contrato",
        config_parameter="gn_hr_employee_warnings.contract_expiration_warning_days",
        default=30,
        help="Mostrar alerta cuando el contrato venza en este número de días o menos.",
    )
    gn_hr_loan_ending_installments_threshold = fields.Integer(
        string="Umbral de cuotas restantes (préstamo en contrato)",
        config_parameter="gn_hr_employee_warnings.loan_ending_installments_threshold",
        default=3,
        help="Mostrar alerta cuando un préstamo activo en conceptos recurrentes tenga este número "
        "de cuotas pendientes o menos (y al menos una). Poner 0 para desactivar esta alerta.",
    )
    gn_hr_low_net_pay_remaining_percent = fields.Integer(
        string="Líquido mínimo vs bruto quincenal",
        config_parameter="gn_hr_employee_warnings.low_net_pay_gross_remaining_percent",
        default=25,
        help="Si el líquido estimado (bruto quincena menos IHSS/RAP/ISR o ISSS/AFP/ISR y deducciones recurrentes) "
        "representa este porcentaje o menos del bruto, se muestra alerta en la ficha (HN y SV). Valor entre 1 y 95.",
    )
