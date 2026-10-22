from odoo import fields, models

class ResUsers(models.Model):
    _inherit = 'res.users'

    branch_id = fields.Many2one('res.branch', 'Branch', required=False)
    branch_ids = fields.Many2many('res.branch',string='Branches')
    journal_default_id = fields.Many2one('account.journal',string="Diario")

class TemplateSettingsInh(models.Model):
    _inherit = "report.template.settings"

    branch_id = fields.Many2one('res.branch', 'Branch')
