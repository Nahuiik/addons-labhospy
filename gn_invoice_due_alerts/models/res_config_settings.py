# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    due_alert_enabled = fields.Boolean(
        related='company_id.due_alert_enabled', readonly=False)
    due_alert_days_before = fields.Integer(
        related='company_id.due_alert_days_before', readonly=False)
    due_alert_include_overdue = fields.Boolean(
        related='company_id.due_alert_include_overdue', readonly=False)
    due_alert_popup_sticky = fields.Boolean(
        related='company_id.due_alert_popup_sticky', readonly=False)
