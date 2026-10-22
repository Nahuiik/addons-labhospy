from odoo import _, api, Command, fields, models
from odoo.exceptions import UserError

_VENDOR_BILL_TYPES = ("in_invoice", "in_refund")
_CUSTOMER_INVOICE_TYPES = ("out_invoice", "out_refund")


class AccountMove(models.Model):
    _inherit = "account.move"

    vendor_invoice_template_id = fields.Many2one(
        "vendor.invoice.template",
        string="Plantilla de Factura",
    )
    applied_vendor_invoice_template_id = fields.Many2one(
        "vendor.invoice.template",
        string="Plantilla Aplicada",
        copy=False,
    )
    header_analytic_distribution = fields.Json(
        "Distribución Analítica (Cabecera)",
    )
    header_analytic_dist_template_id = fields.Many2one(
        "analytic.distribution.template",
        string="Plantilla de Distribución",
        ondelete="set null",
    )
    applied_header_analytic_dist_template_id = fields.Many2one(
        "analytic.distribution.template",
        string="Plantilla Distribución Aplicada",
        copy=False,
    )
    analytic_precision = fields.Integer(
        store=False,
        default=lambda self: self.env["decimal.precision"].precision_get(
            "Percentage Analytic"
        ),
    )

    def action_apply_invoice_template(self):
        self.ensure_one()
        if self.move_type not in _VENDOR_BILL_TYPES:
            raise UserError(
                _("Las plantillas de factura con distribución analítica solo aplican a facturas de proveedor.")
            )
        template = self.vendor_invoice_template_id
        if not template:
            return

        vals = {}
        if template.partner_id:
            vals["partner_id"] = template.partner_id.id
        if template.journal_id:
            vals["journal_id"] = template.journal_id.id
        if template.currency_id:
            vals["currency_id"] = template.currency_id.id

        line_commands = []
        for line in self.invoice_line_ids.filtered(
            lambda l: l.display_type == "product"
        ):
            line_commands.append(Command.delete(line.id))

        for tl in template.line_ids:
            line_commands.append(
                Command.create(
                    {
                        "product_id": tl.product_id.id,
                        "name": tl.name or tl.product_id.display_name,
                        "account_id": tl.account_id.id,
                        "quantity": tl.quantity,
                        "price_unit": tl.price_unit,
                        "tax_ids": [Command.set(tl.tax_ids.ids)],
                        "analytic_distribution": (
                            tl.analytic_distribution
                            or template.analytic_distribution
                        ),
                    }
                )
            )

        vals["invoice_line_ids"] = line_commands
        vals["applied_vendor_invoice_template_id"] = template.id
        self.write(vals)

    def action_apply_analytic_distribution(self):
        self.ensure_one()
        if self.move_type not in _VENDOR_BILL_TYPES:
            raise UserError(
                _("La distribución analítica por plantilla de cabecera solo aplica a facturas de proveedor.")
            )
        template = self.header_analytic_dist_template_id
        if not template or not template.analytic_distribution:
            return
        self.header_analytic_distribution = template.analytic_distribution
        for line in self.invoice_line_ids.filtered(
            lambda l: l.display_type == "product"
        ):
            line.analytic_distribution = template.analytic_distribution
        self.applied_header_analytic_dist_template_id = template.id

    @api.onchange("vendor_invoice_template_id")
    def _onchange_vendor_invoice_template_id_clear_applied(self):
        if not self.vendor_invoice_template_id:
            self.applied_vendor_invoice_template_id = False

    @api.onchange("header_analytic_dist_template_id")
    def _onchange_header_analytic_dist_template_id_clear_applied(self):
        if not self.header_analytic_dist_template_id:
            self.applied_header_analytic_dist_template_id = False

    @api.onchange("move_type")
    def _onchange_move_type_clear_vendor_analytic_fields(self):
        """No dejar plantillas de proveedor si el documento deja de ser factura de proveedor."""
        if self.move_type not in _VENDOR_BILL_TYPES:
            self.vendor_invoice_template_id = False
            self.applied_vendor_invoice_template_id = False
            self.header_analytic_dist_template_id = False
            self.applied_header_analytic_dist_template_id = False
            self.header_analytic_distribution = False

    def _post(self, soft=True):
        """Red de seguridad: no permitir publicar una factura de cliente cuyo
        diario de venta no tenga una distribución analítica configurada.

        Así garantizamos que toda factura de cliente quede con su analítica
        (sucursal) sin depender de que el usuario la cargue manualmente.
        """
        faltantes = self.env["account.move"]
        for move in self:
            if (
                move.move_type in _CUSTOMER_INVOICE_TYPES
                and move.journal_id.type == "sale"
                and not move.journal_id.analytic_distribution
            ):
                faltantes |= move
        if faltantes:
            detalle = "\n".join(
                "  • %s (diario: %s)" % (m.name or _("Borrador"), m.journal_id.name)
                for m in faltantes
            )
            raise UserError(
                _(
                    "No se puede publicar la(s) siguiente(s) factura(s) de cliente "
                    "porque su diario de venta no tiene una distribución analítica "
                    "configurada:\n%s\n\nConfigure la distribución analítica en el "
                    "diario (Contabilidad > Configuración > Diarios) e inténtelo de "
                    "nuevo."
                )
                % detalle
            )
        return super()._post(soft=soft)

    def write(self, vals):
        res = super().write(vals)
        vendor_types = _VENDOR_BILL_TYPES
        to_fix = self.filtered(lambda m: m.move_type not in vendor_types)
        for move in to_fix:
            clear_move = {}
            if move.vendor_invoice_template_id:
                clear_move["vendor_invoice_template_id"] = False
            if move.applied_vendor_invoice_template_id:
                clear_move["applied_vendor_invoice_template_id"] = False
            if move.header_analytic_dist_template_id:
                clear_move["header_analytic_dist_template_id"] = False
            if move.applied_header_analytic_dist_template_id:
                clear_move["applied_header_analytic_dist_template_id"] = False
            if move.header_analytic_distribution:
                clear_move["header_analytic_distribution"] = False
            if clear_move:
                super(AccountMove, move).write(clear_move)
            lines = move.invoice_line_ids.filtered("analytic_dist_template_id")
            if lines:
                lines.write({"analytic_dist_template_id": False})
        return res
