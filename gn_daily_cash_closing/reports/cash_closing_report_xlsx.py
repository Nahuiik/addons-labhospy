# -*- coding: utf-8 -*-
from odoo import models


class CashClosingReportXlsx(models.AbstractModel):
    _name = "report.gn_daily_cash_closing.cash_closing_report_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "Reporte Cierre de Caja Diario XLSX"

    def generate_xlsx_report(self, workbook, data, closings):
        report = self.env["report.gn_daily_cash_closing.cash_closing_template"]
        for closing in closings:
            report_date = closing.date
            branch_id = closing.branch_id.id if closing.branch_id else False
            remesas_data = [
                {
                    "bank_name": r.bank_name or "",
                    "account_number": r.account_number or "",
                    "reference": r.reference or "",
                    "date": str(r.date) if r.date else "",
                    "amount": r.amount or 0,
                }
                for r in closing.remesa_line_ids
            ]
            uid = closing.user_id.id if closing.user_id else False
            ventas = report._get_ventas(report_date, branch_id, user_id=uid)
            ingresos = report._get_ingresos(report_date, branch_id, user_id=uid)
            remesas_sobrantes = sum(
                closing.remesa_sobrante_line_ids.mapped("amount") or [0]
            )
            ingresos["sobrantes"] = ingresos.get("sobrantes", 0) + remesas_sobrantes
            ingresos["total"] = ingresos.get("total", 0) + remesas_sobrantes
            anulaciones = report._get_anulaciones(report_date, branch_id, user_id=uid)
            remesado = report._get_remesado(ingresos, remesas_data)
            liquidacion = report._get_liquidacion(report_date, branch_id)
            docs_ventas = report._get_docs_ventas(report_date, branch_id, user_id=uid)
            docs_cobros, docs_cobros_anticipos = report._get_docs_cobros(
                report_date, branch_id, user_id=uid
            )
            docs_anticipos_presupuesto, docs_anticipos_prefactura = (
                report._get_docs_anticipos_separados(
                    [], {"closing_id": closing.id}, report_date, branch_id
                )
            )

            sheet = workbook.add_worksheet("Cierre de Caja")
            title_fmt = workbook.add_format({
                "bold": True, "font_size": 14, "align": "center",
            })
            header_fmt = workbook.add_format({
                "bold": True, "font_size": 10, "border": 1,
            })
            cell_fmt = workbook.add_format({"font_size": 10, "border": 1})
            money_fmt = workbook.add_format({
                "font_size": 10, "border": 1, "num_format": "#,##0.00",
            })

            sheet.set_column("A:A", 35)
            sheet.set_column("B:B", 15)

            row = 0
            sheet.merge_range(row, 0, row, 1, self.env.company.name, title_fmt)
            row += 1
            sheet.write(row, 0, "Sucursal:", cell_fmt)
            sheet.write(row, 1, closing.branch_id.name or "", cell_fmt)
            row += 1
            sheet.write(row, 0, "Día:", cell_fmt)
            sheet.write(row, 1, str(report_date), cell_fmt)
            row += 2

            sheet.write(row, 0, "VENTAS", header_fmt)
            row += 1
            sheet.write(row, 0, "Ventas de Contado", cell_fmt)
            sheet.write(row, 1, ventas.get("contado", 0), money_fmt)
            row += 1
            sheet.write(row, 0, "Contra Entrega", cell_fmt)
            sheet.write(row, 1, ventas.get("contra_entrega", 0), money_fmt)
            row += 1
            sheet.write(row, 0, "Créditos", cell_fmt)
            sheet.write(row, 1, ventas.get("creditos", 0), money_fmt)
            row += 1
            sheet.write(row, 0, "Total Ventas", header_fmt)
            sheet.write(row, 1, ventas.get("total", 0), money_fmt)
            row += 2

            sheet.write(row, 0, "ANULACIONES Y REBAJAS", header_fmt)
            row += 1
            sheet.write(row, 0, "Ventas Anuladas", cell_fmt)
            sheet.write(row, 1, anulaciones.get("ventas_anuladas", 0), money_fmt)
            row += 1
            sheet.write(row, 0, "Anticipos por Anulaciones", cell_fmt)
            sheet.write(row, 1, anulaciones.get("anticipos_anulaciones", 0), money_fmt)
            row += 1
            sheet.write(row, 0, "Rebajas a Clientes", cell_fmt)
            sheet.write(row, 1, anulaciones.get("rebajas_clientes", 0), money_fmt)
            row += 2

            sheet.write(row, 0, "INGRESOS", header_fmt)
            row += 1
            sheet.write(row, 0, "Efectivo", cell_fmt)
            sheet.write(row, 1, ingresos.get("efectivo", 0), money_fmt)
            row += 1
            sheet.write(row, 0, "Tarjeta", cell_fmt)
            sheet.write(row, 1, ingresos.get("tarjeta", 0), money_fmt)
            row += 1
            sheet.write(row, 0, "Transferencia", cell_fmt)
            sheet.write(row, 1, ingresos.get("transferencia", 0), money_fmt)
            row += 1
            sheet.write(row, 0, "Anticipos Recibidos", cell_fmt)
            sheet.write(row, 1, ingresos.get("anticipos", 0), money_fmt)
            row += 1
            sheet.write(row, 0, "Sobrantes Recibidos", cell_fmt)
            sheet.write(row, 1, ingresos.get("sobrantes", 0), money_fmt)
            row += 1
            sheet.write(row, 0, "Total Ingresos", header_fmt)
            sheet.write(row, 1, ingresos.get("total", 0), money_fmt)
            row += 2

            sheet.write(row, 0, "REMESADO", header_fmt)
            row += 1
            sheet.write(row, 0, "Total Remesado", cell_fmt)
            sheet.write(row, 1, remesado.get("total_remesado", 0), money_fmt)
            row += 1
            sheet.write(row, 0, "Remesado de Más", cell_fmt)
            sheet.write(row, 1, remesado.get("remesado_de_mas", 0), money_fmt)
            row += 1
            sheet.write(row, 0, "No Remesado", cell_fmt)
            sheet.write(row, 1, remesado.get("no_remesado", 0), money_fmt)
            row += 2

            sheet.write(row, 0, "LIQUIDACIÓN DE TARJETAS", header_fmt)
            row += 1
            sheet.write(row, 0, "Monto Venta Liquidado", cell_fmt)
            sheet.write(row, 1, liquidacion.get("monto_venta_liquidado", 0), money_fmt)
            row += 1
            sheet.write(row, 0, "Valor Remesado", cell_fmt)
            sheet.write(row, 1, liquidacion.get("valor_remesado", 0), money_fmt)
            row += 1
            sheet.write(row, 0, "Valor No Remesado", cell_fmt)
            sheet.write(row, 1, liquidacion.get("valor_no_remesado", 0), money_fmt)
            row += 1
            sheet.write(row, 0, "No. Corte Liquidados", cell_fmt)
            sheet.write(row, 1, liquidacion.get("no_corte_liquidados", 0), cell_fmt)
            row += 2

            sheet.write(row, 0, "VENTAS (Documentos)", header_fmt)
            row += 1
            sheet.write(row, 0, "Vendedor", header_fmt)
            sheet.write(row, 1, "Nº Control", header_fmt)
            sheet.write(row, 2, "Tipo", header_fmt)
            sheet.write(row, 3, "Total", header_fmt)
            row += 1
            for dv in docs_ventas:
                sheet.write(row, 0, dv.get("vendedor", ""), cell_fmt)
                sheet.write(row, 1, dv.get("numero_control", ""), cell_fmt)
                sheet.write(row, 2, dv.get("tipo_pago", ""), cell_fmt)
                sheet.write(row, 3, dv.get("total", 0), money_fmt)
                row += 1
            row += 1

            sheet.write(row, 0, "COBROS", header_fmt)
            row += 1
            sheet.write(row, 0, "Diario", header_fmt)
            sheet.write(row, 1, "Nº Control", header_fmt)
            sheet.write(row, 2, "Tipo", header_fmt)
            sheet.write(row, 3, "Total", header_fmt)
            row += 1
            for dc in docs_cobros:
                sheet.write(row, 0, dc.get("diario", ""), cell_fmt)
                sheet.write(row, 1, dc.get("numero_control", ""), cell_fmt)
                sheet.write(row, 2, dc.get("tipo_pago", ""), cell_fmt)
                sheet.write(row, 3, dc.get("total", 0), money_fmt)
                row += 1
            row += 1

            sheet.write(row, 0, "COTIZACIONES CON ANTICIPOS (PRESUPUESTO)", header_fmt)
            row += 1
            sheet.write(row, 0, "Diario", header_fmt)
            sheet.write(row, 1, "Nº Control", header_fmt)
            sheet.write(row, 2, "Tipo", header_fmt)
            sheet.write(row, 3, "Total", header_fmt)
            row += 1
            for dap in docs_anticipos_presupuesto:
                sheet.write(row, 0, dap.get("diario", ""), cell_fmt)
                sheet.write(row, 1, dap.get("numero_control", ""), cell_fmt)
                sheet.write(row, 2, dap.get("tipo_pago", ""), cell_fmt)
                sheet.write(row, 3, dap.get("total", 0), money_fmt)
                row += 1
            row += 1

            sheet.write(row, 0, "COTIZACIONES PRE-FACTURA CON ANTICIPOS", header_fmt)
            row += 1
            sheet.write(row, 0, "Diario", header_fmt)
            sheet.write(row, 1, "Nº Control", header_fmt)
            sheet.write(row, 2, "Tipo", header_fmt)
            sheet.write(row, 3, "Total", header_fmt)
            row += 1
            for daf in docs_anticipos_prefactura:
                sheet.write(row, 0, daf.get("diario", ""), cell_fmt)
                sheet.write(row, 1, daf.get("numero_control", ""), cell_fmt)
                sheet.write(row, 2, daf.get("tipo_pago", ""), cell_fmt)
                sheet.write(row, 3, daf.get("total", 0), money_fmt)
                row += 1
