from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    hn_production_source_warehouse_id = fields.Many2one(
        related="company_id.hn_production_source_warehouse_id",
        readonly=False,
        string="Bodega A (origen materiales)",
    )
    hn_production_dest_warehouse_id = fields.Many2one(
        related="company_id.hn_production_dest_warehouse_id",
        readonly=False,
        string="Bodega de producción",
    )
    hn_production_allow_self_approval = fields.Boolean(
        related="company_id.hn_production_allow_self_approval",
        readonly=False,
        string="Permitir autoaprobación de transferencias",
    )
