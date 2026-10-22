import logging
import os
from collections import defaultdict
from importlib import import_module
from io import BytesIO

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .report_registry import REPORT_REGISTRY, ReportRegistryMixin


_logger = logging.getLogger(__name__)


class DynamicReport(models.Model):
    _name = "dynamic.report"
    _description = "Dynamic Report"
    _inherit = ["mail.thread", "mail.activity.mixin", "custom.dynamic.report.registry.mixin"]

    name = fields.Char(required=True, tracking=True, default=lambda self: self._get_next_name())
    report_type = fields.Selection(selection="_selection_report_type", required=True, tracking=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("generating", "Generating"),
            ("ready", "Ready"),
            ("failed", "Failed"),
        ],
        default="draft",
        tracking=True,
    )
    state_filter = fields.Many2many(
        "ir.model.fields.selection",
        "dynamic_report_state_rel",
        "report_id",
        "selection_id",
        string="States",
        domain="[('field_id.model', '=', 'account.move'), ('field_id.name', '=', 'state'), ('value', 'in', ['draft', 'posted', 'cancel'])]",
        default=lambda self: self._default_state_filter(),
        help="Select the invoice states to include in this report.",
    )
    date_start = fields.Date(tracking=True)
    date_end = fields.Date(tracking=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    line_ids = fields.One2many("dynamic.report.line", "report_id", copy=False)
    line_count = fields.Integer(compute="_compute_line_count", store=True)
    total_amount = fields.Monetary(currency_field="currency_id", tracking=True)
    total_tax = fields.Monetary(currency_field="currency_id", tracking=True)
    total_net = fields.Monetary(currency_field="currency_id", tracking=True)
    generated_at = fields.Datetime(tracking=True)
    error_message = fields.Text(readonly=True)
    parameter_summary = fields.Text(readonly=True)

    _check_name_company_unique = models.Constraint(
        "unique(name, company_id)",
        "The report name must be unique per company.",
    )

    @api.depends("line_ids")
    def _compute_line_count(self):
        for report in self:
            report.line_count = len(report.line_ids)

    @api.model
    def _selection_report_type(self):
        if not REPORT_REGISTRY:
            return []
        return [
            (key, getattr(cls, "label", key.title()))
            for key, cls in REPORT_REGISTRY.items()
        ]

    def _require_pandas(self):
        try:
            pd_module = self._load_pandas()
        except RuntimeError as exc:
            raise UserError(str(exc)) from exc
        return pd_module

    @api.model
    def _get_next_name(self):
        return self.env['ir.sequence'].next_by_code('custom_dynamic_reports.dynamic_report') or _('New')

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') in ('/', _('New')):
                vals['name'] = sequence.next_by_code('custom_dynamic_reports.dynamic_report')
        return super().create(vals_list)

    @api.model
    def _default_state_filter(self):
        field = self.env['ir.model.fields'].sudo().search([
            ('model', '=', 'account.move'),
            ('name', '=', 'state')
        ], limit=1)
        if not field:
            return False
        return self.env['ir.model.fields.selection'].sudo().search([
            ('field_id', '=', field.id),
            ('value', '=', 'posted')
        ])

    def action_generate(self):
        self._require_pandas()
        for report in self:
            generator = self.get_generator(report.report_type, report)
            if not generator:
                raise UserError(_("No generator registered for report type %s") % report.report_type)
            report._generate_with(generator)
        return True

    def _generate_with(self, generator):
        self.ensure_one()
        self.write({"state": "generating", "error_message": False})
        self.line_ids.unlink()
        try:
            lines, aggregates = generator.generate()
        except Exception as exc:  # pragma: no cover - we log full stack in server logs
            _logger.exception("Dynamic report generation failed")
            self.write({
                "state": "failed",
                "error_message": str(exc),
            })
            return

        self._bulk_create_lines(lines)

        values = {
            "state": "ready",
            "generated_at": fields.Datetime.now(),
            "total_amount": aggregates.get("total_amount", 0.0),
            "total_tax": aggregates.get("total_tax", 0.0),
            "total_net": aggregates.get("total_net", 0.0),
            "parameter_summary": self._build_parameter_summary(),
        }
        self.write(values)

    def _bulk_create_lines(self, lines):
        if not lines:
            return
        line_model = self.env["dynamic.report.line"]
        batch_size = 2000
        to_create = []
        for index, line_vals in enumerate(lines, start=1):
            prepared = {
                "report_id": self.id,
                "sequence": index,
                "document_name": line_vals.get("document_name"),
                "document_date": line_vals.get("document_date"),
                "partner_id": line_vals.get("partner_id"),
                "partner_name": line_vals.get("partner_name"),
                "product_id": line_vals.get("product_id"),
                "product_name": line_vals.get("product_name"),
                "category_name": line_vals.get("category_name"),
                "salesperson_name": line_vals.get("salesperson_name"),
                "quantity": line_vals.get("quantity", 0.0),
                "price_unit": line_vals.get("price_unit", 0.0),
                "subtotal": line_vals.get("subtotal", 0.0),
                "tax_amount": line_vals.get("tax_amount", 0.0),
                "total": line_vals.get("total", 0.0),
                "status_label": line_vals.get("status_label"),
                "invoice_state_label": line_vals.get("invoice_state_label"),
                "taxable_amount": line_vals.get("taxable_amount", 0.0),
                "exempt_amount": line_vals.get("exempt_amount", 0.0),
                "discount_amount": line_vals.get("discount_amount", 0.0),
                "cost_unit": line_vals.get("cost_unit", 0.0),
                "cost_total": line_vals.get("cost_total", 0.0),
                "margin_amount": line_vals.get("margin_amount", 0.0),
                "margin_percent": line_vals.get("margin_percent", 0.0),
                "currency_id": line_vals.get("currency_id"),
                "extra_json": line_vals.get("extra_json"),
            }
            to_create.append(prepared)
            if len(to_create) >= batch_size:
                line_model.create(to_create)
                to_create = []
        if to_create:
            line_model.create(to_create)

    def action_view_lines(self):
        self.ensure_one()
        action = self.env.ref("custom_dynamic_reports.action_dynamic_report_lines").read()[0]
        action["domain"] = [["report_id", "=", self.id]]
        action["context"] = {"search_default_group_by_partner_id": 0}
        return action

    def action_open_export_wizard(self):
        self.ensure_one()
        return {
            "name": _("Export Report"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "dynamic.report.export.wizard",
            "target": "new",
            "context": {
                "default_report_id": self.id,
            },
        }

    def _build_parameter_summary(self):
        self.ensure_one()
        parts = [_("Report type: %s") % self._get_report_type_label()]
        if self.date_start:
            parts.append(_("From %s") % fields.Date.to_string(self.date_start))
        if self.date_end:
            parts.append(_("To %s") % fields.Date.to_string(self.date_end))
        return " | ".join(parts)

    def _get_report_type_label(self):
        self.ensure_one()
        field = self._fields["report_type"]
        if callable(field.selection):
            selection_items = field.selection(self.env) or []
        else:
            selection_items = field.selection or []
        selection = {}
        for item in selection_items:
            if isinstance(item, (tuple, list)) and len(item) == 2:
                selection[item[0]] = item[1]
        if not selection:
            selection = {key: getattr(cls, "label", key.title()) for key, cls in REPORT_REGISTRY.items()}
        return selection.get(self.report_type, self.report_type)

    def _lines_to_dataframe(self, pd=None):
        self.ensure_one()
        pd = pd or self._require_pandas()
        data = []
        for line in self.line_ids:
            row = {
                "Secuencia": line.sequence,
                "Fecha": line.document_date,
                "Número de Factura": line.document_name,
                "Producto": line.product_name,
                "Categoría": line.category_name,
                "Cliente": line.partner_name,
                "Comercial": line.salesperson_name,
                "Cantidad": line.quantity,
                "Precio Unitario": line.price_unit,
                "Gravado": line.taxable_amount,
                "Exento": line.exempt_amount,
                "Impuestos": line.tax_amount,
                "Subtotal": line.subtotal,
                "Descuentos": line.discount_amount,
                "Total": line.total,
                "Costo Unitario": line.cost_unit,
                "Costo Total": line.cost_total,
                "Utilidad Bruta": line.margin_amount,
                "% Utilidad": line.margin_percent,
                "Estado Pago": line.status_label,
                "Estado Factura": line.invoice_state_label,
        }
            if line.extra_json:
                row.update(line.extra_json)
            data.append(row)
        columns = [
            "Secuencia",
            "Fecha",
            "Número de Factura",
            "Producto",
            "Categoría",
            "Cliente",
            "Comercial",
            "Cantidad",
            "Precio Unitario",
            "Gravado",
            "Exento",
            "Impuestos",
            "Subtotal",
            "Descuentos",
            "Total",
            "Costo Unitario",
            "Costo Total",
            "Utilidad Bruta",
            "% Utilidad",
            "Estado Pago",
            "Estado Factura",
        ]
        if not data:
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(data, columns=columns)

    def _export_xlsx_bytes(self):
        pd = self._require_pandas()
        dataframe = self._lines_to_dataframe(pd)
        buffer = BytesIO()
        sheet_name = (self.name or "report")[:31]
        dataframe.to_excel(buffer, sheet_name=sheet_name, index=False)
        buffer.seek(0)
        return buffer.getvalue()

    def _get_report_action_pdf(self):
        self.ensure_one()
        return self.env.ref("custom_dynamic_reports.dynamic_report_pdf").report_action(self)

    def _load_pandas(self):
        os.environ.setdefault("NUMEXPR_MAX_THREADS", "4")
        os.environ.setdefault("OMP_NUM_THREADS", "4")
        try:
            pandas_module = import_module("pandas")
        except ImportError as exc:
            raise RuntimeError(
                _(
                    "The Python library 'pandas' is required to generate this report. "
                    "Install it in the Odoo environment and restart the server."
                )
            ) from exc
        required_attrs = ["DataFrame", "Series"]
        if not all(hasattr(pandas_module, attr) for attr in required_attrs):
            raise RuntimeError(
                _(
                    "The installed pandas package appears to be incompatible. "
                    "Reinstall pandas (and, if needed, numpy) matching the Python version."
                )
            )
        try:
            numexpr = import_module("numexpr")
            max_threads = int(os.environ.get("NUMEXPR_MAX_THREADS", "4"))
            numexpr.set_num_threads(max_threads)
        except Exception:  # pragma: no cover - best effort tuning
            pass
        return pandas_module
