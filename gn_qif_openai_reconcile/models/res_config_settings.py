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
    qif_folder_import_root = fields.Char(
        string='Carpeta lote Excel (extractos)',
        config_parameter='gn_qif.folder_import.root',
        default='/home/odoo/zip/BANCOS',
        help='Directorio donde el asistente «Importar carpeta Excel» busca '
             '.xls/.xlsx (y subcarpetas de primer nivel).',
    )
    qif_openai_auto_promote_reconcile_ce = fields.Boolean(
        string='Tras IA: crear modelos de conciliación (Odoo estándar)',
        config_parameter='gn_qif_openai.auto_promote_reconcile',
        help='Por defecto se marca en «Importar EC con IA»: al terminar la IA persisten patrones '
             'y, si existe la cuenta, se crea account.reconcile.model (Community, módulo contable). '
             'Puede desmarcarse en cada análisis.',
    )
