# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    customer_due_alert_enabled = fields.Boolean(
        string='Activar alertas de cobro',
        default=True)
    customer_due_alert_days_before = fields.Integer(
        string='Dias de anticipacion (clientes)',
        default=3,
        help='Dias antes del vencimiento para considerar una factura de '
             'cliente como proxima a vencer y enviar el recordatorio.')
    customer_due_alert_include_overdue = fields.Boolean(
        string='Incluir vencidas en alertas de cobro',
        default=True)
    customer_due_alert_popup_sticky = fields.Boolean(
        string='Notificacion emergente persistente (cobros)',
        default=True)
