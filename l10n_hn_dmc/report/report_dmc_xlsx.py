# -*- coding: utf-8 -*-
import re

from odoo import _, models


class ReportDmcXlsx(models.AbstractModel):
    _name = "report.l10n_hn_dmc.dmc_report_xls"
    _inherit = "report.report_xlsx.abstract"
    _description = "Reporte DMC XLSX"

    def generate_xlsx_report(self, workbook, data, lines):
        sheet = workbook.add_worksheet(_("DMC"))

        date_from = data.get("date_from")
        date_to = data.get("date_to")
        invoices = self.get_data(date_from, date_to)

        format1 = workbook.add_format(
            {
                "font_size": 14,
                "bottom": True,
                "right": True,
                "left": True,
                "top": True,
                "align": "vcenter",
                "bold": True,
            }
        )
        format11 = workbook.add_format(
            {
                "font_size": 12,
                "align": "center",
                "right": True,
                "left": True,
                "bottom": True,
                "top": True,
                "bold": True,
            }
        )
        format3 = workbook.add_format(
            {
                "align": "right",
                "left": False,
                "right": False,
                "bottom": False,
                "top": False,
                "font_size": 10,
                "num_format": "#,##0.00",
                "text_wrap": True,
            }
        )
        format4 = workbook.add_format(
            {
                "align": "right",
                "left": False,
                "right": False,
                "bottom": False,
                "top": False,
                "bold": True,
                "font_size": 10,
                "num_format": "#,##0.00",
            }
        )
        format23 = workbook.add_format(
            {
                "font_size": 10,
                "align": "center",
                "right": True,
                "left": True,
                "bottom": True,
                "top": True,
                "bold": True,
                "bg_color": "#0B2161",
                "font_color": "white",
                "text_wrap": True,
            }
        )

        format1.set_align("center")

        sheet.set_column(0, 0, 3)
        for col in range(1, 28):
            sheet.set_column(col, col, 15 if col != 2 else 40)

        sheet.merge_range("A1:S1", data.get("company_name", ""), format1)
        sheet.merge_range("A2:S2", _("Reporte DMC"), format11)

        sheet.write(4, 0, "", format23)
        sheet.write(4, 1, "200-RTN", format23)
        sheet.write(4, 2, _("PROVEEDOR"), format23)
        sheet.write(4, 3, "600-Clase de documento", format23)
        sheet.write(4, 4, "7-CAI", format23)
        sheet.write(
            4,
            5,
            "8-Nº documento (establecimiento / punto de emisión / tipo documento / correlativo)",
            format23,
        )
        sheet.write(4, 6, "71-Nº documento", format23)
        sheet.write(4, 7, "900-Fecha emisión", format23)
        sheet.write(4, 8, "100-Fecha contable", format23)
        sheet.write(4, 9, "140-Nº OCE", format23)
        sheet.write(4, 10, "110-Importe exento", format23)
        sheet.write(4, 11, "130-Nº resolución", format23)
        sheet.write(4, 12, "1201-Importe exonerado al 15%", format23)
        sheet.write(4, 13, "1202-Importe exonerado al 18%", format23)
        sheet.write(4, 14, "1511-Importe base 15%", format23)
        sheet.write(4, 15, "1611-Importe base 18%", format23)
        sheet.write(4, 16, "270-Monto al costo", format23)
        sheet.write(4, 17, "280-Monto al gasto", format23)
        sheet.write(4, 18, "290-Valor no deducible", format23)

        pos = 5
        for invoice in invoices:
            sheet.write(pos, 1, invoice.get("rtn") or "", format3)
            sheet.write(pos, 2, invoice.get("name") or "", format3)
            sheet.write(pos, 3, invoice.get("doc_class") or "FA-Factura", format3)
            sheet.write(pos, 4, invoice.get("cai") or "", format3)
            sheet.write(pos, 5, invoice.get("document") or "N/A", format3)
            sheet.write(pos, 6, "", format3)
            sheet.write(pos, 7, invoice.get("date") or "N/A", format3)
            sheet.write(pos, 8, invoice.get("date") or "", format3)
            sheet.write(pos, 9, "No", format3)
            sheet.write(pos, 10, invoice.get("exempt_amount"), format3)
            sheet.write(pos, 11, 0.0, format4)
            sheet.write(pos, 12, 0.0, format4)
            sheet.write(pos, 13, 0.0, format4)
            sheet.write(pos, 14, invoice.get("isv_15"), format4)
            sheet.write(pos, 15, invoice.get("isv_18"), format4)
            sheet.write(pos, 16, invoice.get("monto_costo"), format4)
            sheet.write(pos, 17, invoice.get("monto_gasto"), format3)
            sheet.write(pos, 18, 0.0, format3)
            pos += 1

    def _amounts_in_local_currency(self, invoice):
        """Montos DMC en moneda de la compañía (HNL cuando aplica)."""
        exempt = invoice.exempt_sale_amount or 0.0
        isv_15 = invoice.amount_tax_15_per or 0.0
        isv_18 = invoice.amount_tax_18_per or 0.0
        amount_total = invoice.amount_total or 0.0

        if invoice.currency_id == invoice.company_id.currency_id:
            return exempt, isv_15, isv_18, amount_total

        if "amount_local" in invoice._fields:
            amount_total = abs(invoice.amount_local)
        else:
            amount_total = abs(invoice.amount_total_signed)

        amount_untaxed = invoice.amount_untaxed or 0.0
        if not amount_untaxed:
            return 0.0, 0.0, 0.0, amount_total

        untaxed_local = abs(invoice.amount_untaxed_signed)
        ratio = untaxed_local / amount_untaxed
        return (
            exempt * ratio,
            isv_15 * ratio,
            isv_18 * ratio,
            amount_total,
        )

    def get_data(self, date_from, date_to):
        invoices = []
        domain = [
            ("invoice_date", ">=", date_from),
            ("invoice_date", "<=", date_to),
            ("move_type", "=", "in_invoice"),
            ("state", "=", "posted"),
            *self.env["account.move"]._hn_purchase_report_exclusion_domain(),
        ]
        filtered_invoices = self.env["account.move"].search(domain)
        for invoice in filtered_invoices:
            supplier_number = invoice.supplier_invoice_number or ""
            try:
                stablishment = re.findall(r"\d\d\d-", supplier_number)[0].replace("-", "")
                emission_point = re.findall(r"-\d\d\d-", supplier_number)[0].replace("-", "")
                document_type = re.findall(r"-\d\d-", supplier_number)[0].replace("-", "")
                correlative = re.findall(r"-\d{8}", supplier_number)[0].replace("-", "")
                document = f"{stablishment}-{emission_point}-{document_type}-{correlative}"
            except (IndexError, ValueError):
                document = ""

            exempt_amount, isv_15, isv_18, amount_total = self._amounts_in_local_currency(
                invoice
            )
            monto_costo = 0.0
            monto_gasto = 0.0
            if invoice.excluir_compra:
                monto_gasto = amount_total
            else:
                monto_costo = amount_total

            invoices.append(
                {
                    "rtn": invoice.partner_id.rtn,
                    "name": invoice.partner_id.name,
                    "date": self.convert_date(invoice.invoice_date),
                    "doc_class": "FA-Factura",
                    "cai": invoice.cai_shot_compras,
                    "document": document,
                    "exempt_amount": exempt_amount,
                    "monto_costo": monto_costo,
                    "monto_gasto": monto_gasto,
                    "isv_15": isv_15,
                    "isv_18": isv_18,
                }
            )

        invoices.sort(key=lambda x: x["date"], reverse=True)
        return invoices

    def convert_date(self, date):
        if not date:
            return ""
        try:
            return date.strftime("%d/%m/%Y")
        except (AttributeError, ValueError):
            return ""
