from odoo import api, models


class MrpProductionSerials(models.TransientModel):
    _inherit = "mrp.production.serials"

    @api.depends("production_id")
    def _compute_lot_name(self):
        for wizard in self:
            wizard.serial_numbers = "\n".join(
                wizard.production_id.lot_producing_ids.mapped("name")
            )
            if wizard.lot_name:
                continue
            wizard.lot_name = wizard.production_id.lot_producing_ids[:1].name
            if not wizard.lot_name and wizard.production_id:
                production = wizard.production_id
                wizard.lot_name = self.env["stock.lot"]._hn_next_lot_name(
                    production.product_id,
                    company=production.company_id,
                    lot_date=production._hn_lot_name_reference_date(),
                )
