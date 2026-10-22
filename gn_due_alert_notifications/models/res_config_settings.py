# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    gn_due_notif_enabled = fields.Boolean(
        related='company_id.gn_due_notif_enabled', readonly=False)
    gn_due_notif_days_before = fields.Integer(
        related='company_id.gn_due_notif_days_before', readonly=False)
    gn_due_notif_critical_days = fields.Integer(
        related='company_id.gn_due_notif_critical_days', readonly=False)
    gn_due_notif_repeat_hours = fields.Integer(
        related='company_id.gn_due_notif_repeat_hours', readonly=False)
    gn_due_notif_daily_summary_hour = fields.Float(
        related='company_id.gn_due_notif_daily_summary_hour', readonly=False)
    gn_due_notif_realtime_enabled = fields.Boolean(
        related='company_id.gn_due_notif_realtime_enabled', readonly=False)
    gn_due_notif_daily_summary_enabled = fields.Boolean(
        related='company_id.gn_due_notif_daily_summary_enabled', readonly=False)
    gn_due_notif_sound_enabled = fields.Boolean(
        related='company_id.gn_due_notif_sound_enabled', readonly=False)
    gn_due_notif_snooze_days = fields.Integer(
        related='company_id.gn_due_notif_snooze_days', readonly=False)
    gn_due_notif_max_visible_cards = fields.Integer(
        related='company_id.gn_due_notif_max_visible_cards', readonly=False)
    gn_due_notif_default_responsible_id = fields.Many2one(
        related='company_id.gn_due_notif_default_responsible_id', readonly=False)
    gn_due_notif_notify_account_admins = fields.Boolean(
        related='company_id.gn_due_notif_notify_account_admins', readonly=False)
    gn_due_notif_recipient_user_ids = fields.Many2many(
        related='company_id.gn_due_notif_recipient_user_ids', readonly=False)
