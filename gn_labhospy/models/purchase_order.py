from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    gn_labhospy_compra_internacional = fields.Boolean(
        string='Compra internacional',
        default=False,
        copy=False,
        help='Marcar cuando la orden es compra internacional (importación): la factura de proveedor '
        'podrá marcarse como importación y la recepción exigirá el campo de resolución (SC).',
    )

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        if self.gn_labhospy_compra_internacional and 'is_of_import' in self.env['account.move']._fields:
            vals['is_of_import'] = True
        return vals
