from collections import OrderedDict
from importlib import import_module
import logging

from odoo import _, api, models, fields, tools
from odoo.tools.translate import _lt

REPORT_REGISTRY: dict[str, type] = OrderedDict()
_logger = logging.getLogger(__name__)


def register_report(key):
    def decorator(cls):
        REPORT_REGISTRY[key] = cls
        cls._registry_key = key
        return cls

    return decorator


def get_report_class(key):
    return REPORT_REGISTRY.get(key)


class BaseReportGenerator:
    label = ""
    help = ""

    def __init__(self, env, report):
        self.env = env
        self.report = report
        self._pd_cache = None

    def generate(self):
        dataframe, records = self._build_dataframe()
        lines = self._dataframe_to_lines(dataframe, records)
        aggregates = self._dataframe_to_aggregates(dataframe)
        return lines, aggregates

    def _build_dataframe(self):  # pragma: no cover - interface contract
        raise NotImplementedError

    def _dataframe_to_lines(self, dataframe, records):
        if dataframe.empty:
            return []
        dataframe = dataframe.fillna("")
        return dataframe.to_dict(orient="records")

    def _dataframe_to_aggregates(self, dataframe):
        return {
            "line_count": int(len(dataframe.index)) if not dataframe.empty else 0,
        }

    def _pd(self):
        if self._pd_cache is None:
            self._pd_cache = ReportRegistryMixin.import_pandas()
        return self._pd_cache


class ReportRegistryMixin(models.AbstractModel):
    _name = "custom.dynamic.report.registry.mixin"
    _description = "Report Registry helper"

    @api.model
    def get_report_selection(self):
        if not REPORT_REGISTRY:
            return []
        return [
            (key, getattr(cls, "label", key.title()))
            for key, cls in REPORT_REGISTRY.items()
        ]

    @api.model
    def get_report_help(self, key):
        cls = REPORT_REGISTRY.get(key)
        if not cls:
            return ""
        return getattr(cls, "help", "")

    @api.model
    def get_generator(self, key, report):
        cls = get_report_class(key)
        if not cls:
            return None
        return cls(self.env, report)

    @staticmethod
    def import_pandas():
        try:
            pd_module = import_module("pandas")
        except ImportError as exc:  # pragma: no cover - handled at runtime
            raise RuntimeError("pandas library is required for dynamic reports") from exc
        required_attrs = ["DataFrame", "Series"]
        if not all(hasattr(pd_module, attr) for attr in required_attrs):
            raise RuntimeError(
                "The installed pandas package seems incompatible. "
                "Reinstall pandas (and numpy) to match the Python version."
            )
        return pd_module


@register_report("sales")
class SalesReportGenerator(BaseReportGenerator):
    label = _lt("Sales Detailed")
    help = _lt(
        "Detailed sales invoices with line level breakdown including amounts, taxes "
        "and products."
    )

    def _build_dataframe(self):
        report = self.report
        Move = (
            self.env["account.move"]
            .with_company(report.company_id)
            .sudo()
            .with_context(prefetch_fields=False)
        )
        move_domain = [
            ("move_type", "in", ["out_invoice", "out_refund", "out_receipt", "out_invoice_debit", "out_invoice_anticipate"]),
        ]
        if report.date_start:
            move_domain.append(("invoice_date", ">=", report.date_start))
        if report.date_end:
            move_domain.append(("invoice_date", "<=", report.date_end))
        if report.company_id:
            move_domain.append(("company_id", "=", report.company_id.id))

        rows = []
        if report.state_filter:
            move_domain.append(("state", "in", report.state_filter.mapped("value")))

        moves = Move.search(move_domain, order="invoice_date, name, id")
        _logger.info("Sales report moves found: %s for domain %s", len(moves), move_domain)
        for move in moves:
            currency = move.currency_id or move.company_currency_id
            company_currency = move.company_currency_id
            payment_state_label = dict(move._fields["payment_state"].selection).get(move.payment_state, move.payment_state)
            invoice_state_label = {
                "draft": _("Draft"),
                "posted": _("Validated"),
                "cancel": _("Cancelled"),
            }.get(move.state, move.state)
            salesperson = move.invoice_user_id or move.user_id
            convert_date = move.invoice_date or move.date or fields.Date.context_today(self.env)
            for line in move.invoice_line_ids.filtered(lambda l: l.display_type not in ("line_section", "line_note")):
                sequence_number = len(rows) + 1
                gross_amount = line.quantity * line.price_unit
                subtotal = line.price_subtotal or 0.0
                tax_amount = (line.price_total or 0.0) - subtotal
                discount_amount = gross_amount - subtotal
                if tools.float_compare(tax_amount, 0.0, precision_rounding=currency.rounding or 0.01) > 0:
                    taxable_amount = subtotal
                    exempt_amount = 0.0
                else:
                    taxable_amount = 0.0
                    exempt_amount = subtotal
                cost_unit_company = line.product_id.standard_price or 0.0
                if currency == company_currency:
                    cost_unit = cost_unit_company
                else:
                    cost_unit = company_currency._convert(cost_unit_company, currency, move.company_id, convert_date)
                cost_total = cost_unit * line.quantity
                margin_amount = (line.price_total or 0.0) - cost_total
                margin_percent = margin_amount / (line.price_total or 1.0) * 100 if line.price_total else 0.0
                rows.append({
                    "sequence": sequence_number,
                    "document_name": move.name,
                    "document_date": move.invoice_date or move.date,
                    "partner_id": move.commercial_partner_id.id,
                    "partner_name": move.commercial_partner_id.display_name,
                    "product_id": line.product_id.id,
                    "product_name": line.product_id.display_name,
                    "category_name": line.product_id.categ_id.display_name,
                    "salesperson_name": salesperson.display_name if salesperson else False,
                    "quantity": line.quantity,
                    "price_unit": line.price_unit,
                    "subtotal": subtotal,
                    "tax_amount": tax_amount,
                    "total": line.price_total,
                    "status_label": payment_state_label,
                    "invoice_state_label": invoice_state_label,
                    "taxable_amount": taxable_amount,
                    "exempt_amount": exempt_amount,
                    "discount_amount": discount_amount,
                    "cost_unit": cost_unit,
                    "cost_total": cost_total,
                    "margin_amount": margin_amount,
                    "margin_percent": margin_percent,
                    "currency_id": currency.id,
                })

        pd = self._pd()
        if not rows:
            columns = [
                "sequence",
                "document_name",
                "document_date",
                "partner_name",
                "product_name",
                "category_name",
                "salesperson_name",
                "quantity",
                "price_unit",
                "taxable_amount",
                "exempt_amount",
                "tax_amount",
                "subtotal",
                "discount_amount",
                "total",
                "cost_unit",
                "cost_total",
                "margin_amount",
                "margin_percent",
                "status_label",
                "invoice_state_label",
            ]
            return pd.DataFrame(columns=columns), []

        dataframe = pd.DataFrame(rows)
        return dataframe, rows

    def _dataframe_to_aggregates(self, dataframe):
        if dataframe.empty:
            return {
                "line_count": 0,
                "total_amount": 0.0,
                "total_tax": 0.0,
                "total_net": 0.0,
            }
        return {
            "line_count": int(len(dataframe.index)),
            "total_amount": float(dataframe["total"].sum()),
            "total_tax": float(dataframe["tax_amount"].sum()),
            "total_net": float(dataframe["subtotal"].sum()),
        }
