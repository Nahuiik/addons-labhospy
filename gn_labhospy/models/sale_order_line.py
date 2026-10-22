from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    gn_labhospy_supplier_id = fields.Many2one(
        related='product_template_id.gn_labhospy_supplier_id',
        string='Proveedor (LabHosPy)',
        store=False,
        readonly=True,
    )
    gn_labhospy_catalog_code = fields.Char(
        related='product_template_id.gn_labhospy_catalog_code',
        string='Código de Catálogo',
        readonly=True,
    )
    gn_labhospy_model = fields.Char(
        related='product_template_id.gn_labhospy_model',
        string='Modelo',
        readonly=True,
    )
    gn_labhospy_is_controlled = fields.Boolean(
        related='product_template_id.gn_labhospy_is_controlled',
        string='Producto Controlado',
        readonly=True,
    )
    gn_labhospy_application_use_id = fields.Many2one(
        'gn.labhospy.application.use',
        string='Aplicación / uso',
        domain="[]",
        help='Catálogo compartido con Inventario; útil también en líneas sin producto controlado.',
    )
    gn_labhospy_application_use = fields.Text(
        string='Aplicación de uso (texto)',
        help='Texto libre si necesita complementar la opción elegida del catálogo.',
    )

    @api.onchange('product_id')
    def _onchange_product_id_gn_labhospy_application_use(self):
        for line in self:
            tmpl = line.product_template_id
            if tmpl and tmpl.gn_labhospy_application_use_id:
                line.gn_labhospy_application_use_id = tmpl.gn_labhospy_application_use_id

    def _prepare_invoice_line(self, **optional_values):
        vals = super()._prepare_invoice_line(**optional_values)
        if self.product_id and vals.get('display_type', 'product') == 'product':
            vals['gn_labhospy_application_use_id'] = self.gn_labhospy_application_use_id.id
            vals['gn_labhospy_application_use'] = self.gn_labhospy_application_use
        return vals

    def _gn_has_blocking_invoice_lines(self):
        self.ensure_one()
        return bool(self._get_invoice_lines().filtered(
            lambda line: line.parent_state == 'posted'
        ))

    def _gn_has_delivered_qty(self):
        self.ensure_one()
        rounding = self.product_uom_id.rounding or 0.01
        return float_compare(self.qty_delivered, 0.0, precision_rounding=rounding) > 0

    def _check_line_unlink(self):
        """Permite eliminar líneas confirmadas sin entrega ni factura publicada."""
        return self.filtered(
            lambda line:
                line.state == 'sale'
                and not line.display_type
                and (line._gn_has_delivered_qty() or line._gn_has_blocking_invoice_lines())
        )

    @api.ondelete(at_uninstall=False)
    def _unlink_except_confirmed(self):
        blocked = self._check_line_unlink()
        if blocked:
            raise UserError(_(
                'No se puede eliminar la línea «%(product)s»: ya tiene entregas '
                'o facturas publicadas. Reduzca la cantidad a 0 si aún no hay movimientos.',
                product=blocked[0].product_id.display_name or blocked[0].name,
            ))

