from odoo import fields, models


class StockLocation(models.Model):
    _inherit = "stock.location"

    allow_negative_stock = fields.Boolean(string="Allow Negative Stock")
    check_serial_no = fields.Boolean(
        default=True,
        string="Check Serial No.",
        help=(
            "Si está marcado, se validará que los números de serie estén disponibles "
            "al reservar o mover productos; se lanzará un error si el número de serie "
            "está reservado en otro movimiento o no está disponible."
        ),
    )





