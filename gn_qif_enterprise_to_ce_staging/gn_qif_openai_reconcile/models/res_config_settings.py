from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    qif_openai_api_key = fields.Char(
        string='OpenAI API Key',
        config_parameter='gn_qif_openai.api_key',
    )
    qif_openai_model = fields.Char(
        string='Modelo OpenAI',
        config_parameter='gn_qif_openai.model',
        default='gpt-4.1-mini',
    )
