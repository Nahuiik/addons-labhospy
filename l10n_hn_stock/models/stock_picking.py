from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    product_consume_id = fields.Many2one(
        "consume.product",
        string="Consumo / ingreso interno",
        copy=False,
        index="btree_not_null",
    )

    # Odoo 19 eliminó move_ids_without_package en stock.picking; las vistas/reportes
    # antiguos en BD siguen llamándolo. Misma lógica que el albarán (move_ids filtrados).
    move_ids_without_package = fields.Many2many(
        "stock.move",
        compute="_compute_move_ids_without_package",
        string="Movimientos (sin paquete, compat. reporte)",
        help="Compatible con plantillas QWeb que usan move_ids_without_package (Odoo ≤16).",
    )

    hn_remission_enabled = fields.Boolean(
        string="Guía de remisión",
        tracking=True,
    )
    salesperson_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        tracking=True,
        compute="_compute_remission_related_values",
        store=True,
        readonly=True,
    )
    invoice_name = fields.Char(
        string="Invoice Number",
        compute="_compute_remission_related_values",
        store=True,
        readonly=True,
    )
    hn_remission_number = fields.Char(
        string="Remission Number",
        readonly=True,
        copy=False,
    )

    @api.depends("move_ids", "move_ids.state", "move_ids.product_uom_qty")
    def _compute_move_ids_without_package(self):
        for picking in self:
            picking.move_ids_without_package = picking.move_ids.filtered(
                lambda m: m.state != "cancel" and m.product_uom_qty
            )

    @api.depends(
        "origin",
        "sale_id",
        "sale_id.user_id",
        "sale_id.invoice_ids.state",
        "sale_id.invoice_ids.move_type",
        "sale_id.invoice_ids.invoice_origin",
        "sale_id.invoice_ids.invoice_date",
        "sale_id.invoice_ids.create_date",
    )
    def _compute_remission_related_values(self):
        AccountMove = self.env["account.move"]
        for picking in self:
            salesperson = False
            invoice_name = False

            order = picking.sale_id
            if not order and picking.origin:
                order = self.env["sale.order"].search(
                    [("name", "=", picking.origin)], limit=1
                )

            if order:
                salesperson = order.user_id
                invoices = order.invoice_ids.filtered(
                    lambda m: m.move_type in ("out_invoice", "out_refund")
                    and m.state != "cancel"
                )
                if not invoices:
                    invoices = AccountMove.search(
                        [
                            ("move_type", "in", ("out_invoice", "out_refund")),
                            ("invoice_origin", "=", order.name),
                            ("state", "!=", "cancel"),
                        ],
                        limit=1,
                        order="invoice_date desc, create_date desc, id desc",
                    )
                else:
                    invoices = invoices.sorted(
                        key=lambda m: (
                            m.invoice_date
                            or (m.create_date and m.create_date.date())
                            or date.min,
                            m.id,
                        ),
                        reverse=True,
                    )
                invoice = invoices[0] if invoices else False
                if invoice:
                    invoice_name = invoice.name

            picking.salesperson_id = salesperson
            picking.invoice_name = invoice_name

    def action_generate_remission_sequence(self):
        self.ensure_one()
        if self.hn_remission_number:
            raise UserError(_("The remission sequence is already generated."))
        remission_number = self.env["ir.sequence"].next_by_code("hn.remission")
        if not remission_number:
            raise UserError(_("The remission sequence is not configured."))
        self.write({"hn_remission_number": remission_number})
        return True

    def action_print_remission_guide(self):
        self.ensure_one()
        if not self.hn_remission_number:
            raise UserError(_("Generate the remission sequence before printing."))
        return self.env.ref("l10n_hn_stock.action_report_remission").report_action(
            self
        )

    def _action_done(self):
        res = super()._action_done()
        for picking in self:
            doc = picking.product_consume_id
            if not doc or doc.state != "confirm":
                continue
            if not doc.picking_ids.filtered(lambda p: p.state == "done"):
                continue
            if doc.picking_ids.filtered(
                lambda p: p.state not in ("done", "cancel")
            ):
                continue
            doc.write({"state": "done"})
            doc._create_account_moves()
        return res

