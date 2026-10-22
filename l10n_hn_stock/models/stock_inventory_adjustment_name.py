# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class StockInventoryAdjustmentName(models.TransientModel):
    _inherit = "stock.inventory.adjustment.name"

    # Vista heredada antigua / depuración: mantener campo para no romper vistas en BD.
    periodic_valuation_warning = fields.Text(
        compute="_compute_periodic_valuation_warning",
        help="Aviso cuando la valoración no es en tiempo real (no se generan asientos automáticos).",
    )

    def _l10n_hn_inventory_dates_enabled(self):
        """Compañía del ajuste (o compañía actual si aún no hay cuantías)."""
        self.ensure_one()
        company = self.quant_ids[:1].company_id if self.quant_ids else self.env.company
        return company.l10n_hn_stock_inventory_dates_enabled()

    @api.depends("quant_ids", "quant_ids.product_id")
    def _compute_periodic_valuation_warning(self):
        for wizard in self:
            if not wizard._l10n_hn_inventory_dates_enabled():
                wizard.periodic_valuation_warning = False
                continue
            wizard.periodic_valuation_warning = wizard._periodic_valuation_message() or False

    def _periodic_valuation_message(self):
        """Texto de aviso si hay productos con valoración periódica (sin asiento automático)."""
        self.ensure_one()
        products = self.quant_ids.product_id
        periodic = products.filtered(lambda p: p.valuation == "periodic")
        if not periodic:
            return False
        names = ", ".join(periodic[:8].mapped("display_name"))
        if len(periodic) > 8:
            names += _(" (y %s productos más)") % (len(periodic) - 8)
        return _(
            "Productos con valoración de inventario PERIÓDICA: %(names)s.\n\n"
            "En este modo Odoo no genera asientos contables al validar el ajuste de inventario "
            "(solo movimientos de stock). Para asientos automáticos, en la categoría del producto "
            "configure «Valoración de inventario: Automatizada», con cuentas de valoración de stock "
            "y diario de existencias en la categoría o en la compañía.",
            names=names,
        )

    def _get_quants_context(self):
        res = super()._get_quants_context()
        if not self._l10n_hn_inventory_dates_enabled():
            return res
        # Fecha efectiva única para el asiento de valoración: fecha contable si existe; si no, día del conteo.
        # (super/stock_account ya pusieron force_period_date desde accounting_date; aquí alineamos el hueco.)
        if self.accounting_date:
            res["force_period_date"] = self.accounting_date
        elif self.counting_date:
            res["force_period_date"] = fields.Date.to_date(self.counting_date)
        return res

    @api.onchange("accounting_date")
    def _onchange_accounting_date_sync_counting(self):
        if not self._l10n_hn_inventory_dates_enabled():
            return
        if self.accounting_date:
            self.counting_date = fields.Datetime.to_datetime(self.accounting_date)

    @api.onchange("counting_date")
    def _onchange_counting_date_sync_accounting(self):
        if not self._l10n_hn_inventory_dates_enabled():
            return
        if not self.counting_date or not self.should_show_accounting_date:
            return
        self.accounting_date = fields.Date.to_date(self.counting_date)

