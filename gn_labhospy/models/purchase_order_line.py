from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    gn_labhospy_is_controlled = fields.Boolean(
        related='product_id.product_tmpl_id.gn_labhospy_is_controlled',
        string='Producto controlado',
        readonly=True,
        store=False,
    )

    def _gn_has_blocking_bill_lines(self):
        self.ensure_one()
        return bool(self._get_invoice_lines().filtered(
            lambda line: line.parent_state == 'posted'
        ))

    def _gn_has_received_qty(self):
        self.ensure_one()
        rounding = self.product_uom_id.rounding or 0.01
        return float_compare(self.qty_received, 0.0, precision_rounding=rounding) > 0

    @api.ondelete(at_uninstall=False)
    def _unlink_except_purchase(self):
        """Permite eliminar líneas confirmadas sin recepción ni factura publicada."""
        for line in self:
            if line.display_type in ('line_section', 'line_subsection', 'line_note'):
                continue
            if line.order_id.state != 'purchase':
                continue
            if line._gn_has_received_qty() or line._gn_has_blocking_bill_lines():
                raise UserError(_(
                    'No se puede eliminar la línea «%(product)s»: ya tiene recepciones '
                    'o facturas de proveedor publicadas. Reduzca la cantidad a 0 si '
                    'aún no hay movimientos.',
                    product=line.product_id.display_name or line.name,
                ))
