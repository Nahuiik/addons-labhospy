# -*- coding: utf-8 -*-

from odoo import fields, models

class PosConfig(models.Model):
    _inherit = 'pos.config'
    
    allow_pdf_download = fields.Boolean('Allow PDF Download', default=True)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    pos_allow_pdf_download = fields.Boolean(related='pos_config_id.allow_pdf_download', readonly=False)
