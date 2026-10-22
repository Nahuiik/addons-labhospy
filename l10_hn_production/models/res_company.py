from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    hn_production_source_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Bodega A (origen materiales)",
        check_company=True,
        help="Almacén del que se solicitarán los componentes para producción.",
    )
    hn_production_dest_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Bodega de producción",
        check_company=True,
        help="Almacén donde se valida el inventario disponible antes de transferir.",
    )
    hn_production_allow_self_approval = fields.Boolean(
        string="Permitir autoaprobación",
        default=True,
        help=(
            "Si está activo, un responsable puede aprobar solicitudes que él mismo "
            "generó desde la orden de producción."
        ),
    )

    @api.constrains(
        "hn_production_source_warehouse_id",
        "hn_production_dest_warehouse_id",
    )
    def _check_hn_production_warehouses(self):
        for company in self:
            src = company.hn_production_source_warehouse_id
            dest = company.hn_production_dest_warehouse_id
            if src and dest and src == dest:
                raise ValidationError(
                    _("La Bodega A y la Bodega de producción deben ser diferentes.")
                )
