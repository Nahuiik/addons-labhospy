from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    no_negative_stock = fields.Boolean(
        string="No negative stock",
        help="Prohíbe que los movimientos generen existencias negativas en las ubicaciones internas.",
    )
    hn_consume_dest_location_id = fields.Many2one(
        "stock.location",
        string="Ubicación destino consumo / Desecho",
        check_company=True,
        domain="[('usage', '=', 'inventory'), '|', ('company_id', '=', False), ('company_id', '=', id)]",
        help="Destino fijo del movimiento de consumo (p. ej. ubicación de descarte).",
    )

    @api.constrains("hn_consume_dest_location_id")
    def _check_hn_consume_company_stock_links(self):
        for company in self:
            loc = company.hn_consume_dest_location_id
            if loc and loc.usage != "inventory":
                raise ValidationError(
                    _("La ubicación de destino de consumo debe ser de tipo inventario.")
                )

    def l10n_hn_stock_inventory_dates_enabled(self):
        """Opción guardada en ir.config_parameter (sin columna en res_company)."""
        self.ensure_one()
        key = "l10n_hn_stock.inventory_accounting_dates.%s" % self.id
        return self.env["ir.config_parameter"].sudo().get_param(key, "False") == "True"


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    no_negative_stock = fields.Boolean(
        related="company_id.no_negative_stock",
        string="No negative stock",
        readonly=False,
        help="Prohíbe que los movimientos generen existencias negativas en las ubicaciones internas.",
    )
    hn_consume_dest_location_id = fields.Many2one(
        related="company_id.hn_consume_dest_location_id",
        readonly=False,
        string="Ubicación destino consumo",
    )
    l10n_hn_stock_inventory_accounting_dates = fields.Boolean(
        string="Ajustes de inventario: fechas contables alineadas (HN)",
        help="Activa la lógica de Honduras para alinear fechas contables y de stock en ajustes, "
        "y el reintento de asiento de valoración. Desactivado = comportamiento estándar de Odoo.",
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        company = self.env.company
        key = "l10n_hn_stock.inventory_accounting_dates.%s" % company.id
        res["l10n_hn_stock_inventory_accounting_dates"] = (
            self.env["ir.config_parameter"].sudo().get_param(key, "False") == "True"
        )
        return res

    def set_values(self):
        super().set_values()
        key = "l10n_hn_stock.inventory_accounting_dates.%s" % self.env.company.id
        self.env["ir.config_parameter"].sudo().set_param(
            key, "True" if self.l10n_hn_stock_inventory_accounting_dates else "False"
        )
