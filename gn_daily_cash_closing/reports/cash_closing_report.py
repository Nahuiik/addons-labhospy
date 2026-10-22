# -*- coding: utf-8 -*-
import logging
from collections import OrderedDict
from datetime import datetime, timedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

# Zona horaria por defecto para El Salvador (UTC-6)
DEFAULT_TZ = "America/El_Salvador"

DTE_TYPE_MAP = {
    "01": "CONSUMIDOR FINAL",
    "03": "CREDITO FISCAL",
    "05": "NOTA DE CREDITO",
    "06": "NOTA DE DEBITO",
    "14": "FACTURA SUJETO EXCLUIDO",
}


class CashClosingReport(models.AbstractModel):
    _name = "report.gn_daily_cash_closing.cash_closing_template"
    _description = "Reporte Cierre de Caja Diario"

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        company = self.env.company
        report_date = fields.Date.to_date(data.get("date"))
        branch_id = data.get("branch_id")
        branch_name = data.get("branch_name", "")
        observaciones = data.get("observaciones", "")
        remesas_data = data.get("remesas", [])
        user_id = data.get("user_id")

        branch = self.env["res.branch"].browse(branch_id) if branch_id else False

        ventas = self._get_ventas(report_date, branch_id, user_id=user_id)
        ingresos = self._get_ingresos(report_date, branch_id, user_id=user_id)
        remesas_sobrantes = data.get("remesas_sobrantes", 0) or 0
        ingresos["sobrantes"] = ingresos.get("sobrantes", 0) + remesas_sobrantes
        ingresos["total"] = ingresos.get("total", 0) + remesas_sobrantes
        anulaciones = self._get_anulaciones(report_date, branch_id, user_id=user_id)
        remesado = self._get_remesado(ingresos, remesas_data)
        liquidacion = self._get_liquidacion(report_date, branch_id)
        docs_ventas = self._get_docs_ventas(report_date, branch_id, user_id=user_id)
        docs_cobros, docs_cobros_anticipos = self._get_docs_cobros(report_date, branch_id, user_id=user_id)
        docs_anticipos_presupuesto, docs_anticipos_prefactura = (
            self._get_docs_anticipos_separados(docids, data, report_date, branch_id)
        )
        docs_traslados = self._get_docs_traslados(report_date, branch_id, company)

        branch_code = branch.branch_code or "XX" if branch else "XX"
        no_partida = "N-VE%s%s" % (
            report_date.strftime("%m%d") if report_date else "0000",
            "",
        )
        print_date = self._get_print_date_local(company)

        user_name = data.get("user_name", "")
        return {
            "doc_ids": docids,
            "doc_model": "gn.cash.closing.wizard",
            "company": company,
            "report_date": report_date,
            "branch_name": branch_name,
            "vendedor_name": user_name,
            "encargada": self.env.user.name,
            "no_partida": no_partida,
            "ventas": ventas,
            "ingresos": ingresos,
            "anulaciones": anulaciones,
            "remesado": remesado,
            "liquidacion": liquidacion,
            "remesas_data": remesas_data,
            "docs_ventas": docs_ventas,
            "docs_cobros": docs_cobros,
            "docs_cobros_anticipos": docs_cobros_anticipos,
            "docs_anticipos_presupuesto": docs_anticipos_presupuesto,
            "docs_anticipos_prefactura": docs_anticipos_prefactura,
            "docs_traslados": docs_traslados,
            "observaciones": observaciones,
            "elaborado": self.env.user.name,
            "print_date": print_date,
            "no_partida_contab": "%s%s%s" % (
                report_date.strftime("%Y%m") if report_date else "",
                branch_code,
                report_date.strftime("%d") if report_date else "",
            ),
            "fmt": self._fmt,
        }

    def _get_tz(self, company=None):
        """Obtiene la zona horaria de la compañía o America/El_Salvador por defecto."""
        company = company or self.env.company
        tz_name = (company.partner_id.tz if company and company.partner_id else None) or DEFAULT_TZ
        try:
            import pytz
            return pytz.timezone(tz_name)
        except Exception:
            try:
                import pytz
                return pytz.timezone(DEFAULT_TZ)
            except Exception:
                return None

    def _get_print_date_local(self, company):
        """Fecha/hora de impresión en zona horaria de la compañía (El Salvador UTC-6)."""
        tz = self._get_tz(company)
        if tz:
            return datetime.now(tz).strftime("%d/%m/%Y %H:%M")
        return datetime.now().strftime("%d/%m/%Y %H:%M")

    def _get_date_range_utc(self, report_date, company):
        """
        Convierte report_date (Date) al rango [inicio, fin) del día en TZ de la compañía,
        devuelto como datetimes UTC naive para comparar con scheduled_date (almacenado en UTC).
        """
        if not report_date:
            return None, None
        tz = self._get_tz(company)
        if not tz:
            # Sin pytz: usar medianoche UTC (comportamiento anterior)
            start = datetime.combine(report_date, datetime.min.time())
            end = start + timedelta(days=1)
            return start, end
        try:
            import pytz
            start_local = tz.localize(datetime.combine(report_date, datetime.min.time()))
            end_local = tz.localize(datetime.combine(report_date + timedelta(days=1), datetime.min.time()))
            start_utc = start_local.astimezone(pytz.UTC).replace(tzinfo=None)
            end_utc = end_local.astimezone(pytz.UTC).replace(tzinfo=None)
            return start_utc, end_utc
        except Exception:
            start = datetime.combine(report_date, datetime.min.time())
            end = start + timedelta(days=1)
            return start, end

    # ----------------------------------------------------------------
    # VENTAS
    # ----------------------------------------------------------------
    def _get_ventas(self, report_date, branch_id, user_id=False):
        domain = [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
        ]
        if branch_id:
            domain.append(("branch_id", "=", branch_id))
        if user_id:
            domain.append(("invoice_user_id", "=", user_id))

        invoices = self.env["account.move"].search(domain)
        if report_date:
            invoices = invoices.filtered(
                lambda m: (m.invoice_date or m.date) == report_date
            )

        # Ventas Contado: suma total de facturas con pagos completos
        pagadas = invoices.filtered(lambda i: i.payment_state == "paid")
        contado = sum(abs(inv.amount_total_signed or 0) for inv in pagadas)

        # Contra entrega: suma total de facturas con pagos parciales
        parciales = invoices.filtered(
            lambda i: i.payment_state in ("partial", "in_payment")
        )
        contra_entrega = sum(abs(inv.amount_total_signed or 0) for inv in parciales)

        # Créditos: suma total de facturas abiertas (sin pago)
        abiertas = invoices.filtered(lambda i: i.payment_state == "not_paid")
        creditos = sum(abs(inv.amount_total_signed or 0) for inv in abiertas)

        return {
            "contado": contado,
            "contra_entrega": contra_entrega,
            "creditos": creditos,
            "total": sum(invoices.mapped("amount_total_signed")),
        }

    # ----------------------------------------------------------------
    # INGRESOS (pagos recibidos) - segmentado por Efectivo/Tarjeta/Transferencia
    # ----------------------------------------------------------------
    def _get_payment_mode(self, journal):
        """Devuelve 'efectivo', 'tarjeta' o 'transferencia' según el diario."""
        if not journal:
            return "transferencia"
        if hasattr(journal, "payment_mode") and journal.payment_mode in (
            "efectivo",
            "tarjeta",
            "transferencia",
        ):
            return journal.payment_mode
        if journal.type == "cash":
            return "efectivo"
        if journal.type == "bank":
            if hasattr(journal, "is_credit_card") and journal.is_credit_card:
                return "tarjeta"
            return "transferencia"
        return "transferencia"

    def _get_ingresos(self, report_date, branch_id, user_id=False):
        domain = [
            ("payment_type", "=", "inbound"),
            ("state", "in", ["in_process", "paid"]),
        ]
        if report_date:
            domain.append(("date", "=", report_date))
        if branch_id:
            domain.append(("branch_id", "=", branch_id))

        payments = self.env["account.payment"].search(domain)
        if user_id:
            payments = payments.filtered(
                lambda p: (
                    any(inv.invoice_user_id.id == user_id for inv in p.reconciled_invoice_ids)
                    if not getattr(p, "is_advance", False)
                    else self._advance_belongs_to_user(p, user_id)
                )
            )

        efectivo = tarjeta = transferencia = anticipos = sobrantes = 0.0
        for pay in payments:
            mode = self._get_payment_mode(pay.journal_id)
            amount = pay.amount or 0.0
            is_advance = getattr(pay, "is_advance", False)
            if is_advance:
                anticipos += amount
            else:
                if mode == "efectivo":
                    efectivo += amount
                elif mode == "tarjeta":
                    tarjeta += amount
                else:
                    transferencia += amount

        total = efectivo + tarjeta + transferencia + anticipos + sobrantes
        return {
            "efectivo": efectivo,
            "tarjeta": tarjeta,
            "transferencia": transferencia,
            "anticipos": anticipos,
            "sobrantes": sobrantes,
            "venta_contado": efectivo,  # compatibilidad
            "cobros_clientes": tarjeta + transferencia,  # compatibilidad
            "total": total,
        }

    def _advance_belongs_to_user(self, pay, user_id):
        """Verifica si un anticipo pertenece al vendedor a través de la orden de venta."""
        orders = self.env["sale.order"]
        if "sale_order_id" in pay._fields and pay.sale_order_id:
            orders |= pay.sale_order_id
        if "sale_order_advance_link_ids" in pay._fields and pay.sale_order_advance_link_ids:
            orders |= pay.sale_order_advance_link_ids.mapped("sale_order_id")
        return any(o.user_id.id == user_id for o in orders)

    # ----------------------------------------------------------------
    # ANULACIONES Y REBAJAS
    # ----------------------------------------------------------------
    def _get_anulaciones(self, report_date, branch_id, user_id=False):
        base_domain = []
        if branch_id:
            base_domain.append(("branch_id", "=", branch_id))
        if user_id:
            base_domain.append(("invoice_user_id", "=", user_id))

        cancel_domain = base_domain + [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "cancel"),
        ]
        cancelled = self.env["account.move"].search(cancel_domain)
        if report_date:
            cancelled = cancelled.filtered(
                lambda m: (m.invoice_date or m.date) == report_date
            )

        refund_domain = base_domain + [
            ("move_type", "=", "out_refund"),
            ("state", "=", "posted"),
        ]
        refunds = self.env["account.move"].search(refund_domain)
        if report_date:
            refunds = refunds.filtered(
                lambda m: (m.invoice_date or m.date) == report_date
            )

        anticipos_anulaciones = 0.0
        try:
            AdvanceLink = self.env["account.advance.link"]
            link_domain = [
                ("state", "=", "reversed"),
                ("move_id.state", "=", "cancel"),
            ]
            if report_date:
                link_domain.append(
                    ("move_id.invoice_date", "=", report_date),
                )
            if branch_id and "branch_id" in self.env["account.move"]._fields:
                link_domain.append(("move_id.branch_id", "=", branch_id))
            links = AdvanceLink.search(link_domain)
            anticipos_anulaciones = sum(l.amount or 0.0 for l in links)
        except KeyError:
            pass

        return {
            "ventas_anuladas": sum(abs(m.amount_total) for m in cancelled),
            "anticipos_anulaciones": anticipos_anulaciones,
            "rebajas_clientes": sum(abs(m.amount_total) for m in refunds),
        }

    # ----------------------------------------------------------------
    # REMESADO
    # ----------------------------------------------------------------
    def _get_remesado(self, ingresos, remesas_data):
        total_remesado = sum(r.get("amount", 0) for r in remesas_data)
        total_ingresos = ingresos.get("total", 0)
        diff = total_remesado - total_ingresos
        return {
            "total_remesado": total_remesado,
            "remesado_de_mas": diff if diff > 0 else 0.0,
            "no_remesado": abs(diff) if diff < 0 else 0.0,
        }

    # ----------------------------------------------------------------
    # LIQUIDACION DE TARJETAS (desde debit.credit si gn_banks instalado)
    # ----------------------------------------------------------------
    def _get_liquidacion(self, report_date, branch_id):
        default_result = {
            "monto_venta_liquidado": 0.0,
            "valor_remesado": 0.0,
            "valor_no_remesado": 0.0,
            "no_corte_liquidados": 0,
        }
        try:
            DebitCredit = self.env["debit.credit"]
        except KeyError:
            return default_result
        domain = [
            ("move_type", "=", "credit_card"),
            ("state", "=", "validated"),
        ]
        if report_date:
            domain.append(("date", "=", report_date))
        if branch_id:
            domain.append(("branch_id", "=", branch_id))
        records = DebitCredit.search(domain)
        total = sum(r.total or 0.0 for r in records)
        return {
            "monto_venta_liquidado": total,
            "valor_remesado": total,
            "valor_no_remesado": 0.0,
            "no_corte_liquidados": len(records),
        }

    def _get_payment_mode_label(self, mode):
        """Etiqueta para mostrar en el reporte: Efectivo, Tarjeta, Transferencia, Anticipo."""
        labels = {
            "efectivo": _("Efectivo"),
            "tarjeta": _("Tarjeta"),
            "transferencia": _("Transferencia"),
            "anticipo": _("Anticipo"),
        }
        return labels.get(mode, mode or "")

    def _get_invoice_payment_type(self, invoice):
        """Determina el tipo de pago de una factura: Efectivo, Tarjeta, Transferencia o Anticipo.
        Si tiene varios pagos, devuelve los tipos separados por coma. Si no está pagada: Crédito."""
        if invoice.payment_state == "not_paid":
            return _("Crédito")
        payments = (
            getattr(invoice, "reconciled_payment_ids", None)
            or getattr(invoice, "matched_payment_ids", None)
            or self.env["account.payment"]
        )
        if not payments:
            return _("Crédito")
        modes = set()
        for pay in payments:
            if getattr(pay, "is_advance", False):
                modes.add("anticipo")
            else:
                mode = self._get_payment_mode(pay.journal_id)
                modes.add(mode)
        labels = [self._get_payment_mode_label(m) for m in sorted(modes)]
        return ", ".join(labels) if labels else _("Crédito")

    # ----------------------------------------------------------------
    # DOCUMENTOS ANEXOS - VENTAS (factura por factura, con vendedor y número de control)
    # ----------------------------------------------------------------
    def _get_docs_ventas(self, report_date, branch_id, user_id=False):
        domain = [
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("state", "=", "posted"),
        ]
        if branch_id:
            domain.append(("branch_id", "=", branch_id))
        if user_id:
            domain.append(("invoice_user_id", "=", user_id))

        invoices = self.env["account.move"].search(domain, order="name")
        if report_date:
            invoices = invoices.filtered(
                lambda m: (m.invoice_date or m.date) == report_date
            )

        result = []
        for inv in invoices:
            user = inv.invoice_user_id
            vendedor = user.name if user else _("Sin vendedor")
            ctrl = getattr(inv, "l10n_sv_control_number", "") or inv.name or ""
            tipo_pago = self._get_invoice_payment_type(inv)
            result.append({
                "vendedor": vendedor,
                "numero_control": ctrl,
                "tipo_pago": tipo_pago,
                "total": abs(inv.amount_total_signed),
            })
        return result

    # ----------------------------------------------------------------
    # DOCUMENTOS ANEXOS - COBROS (separados: cobros normales y cobros de anticipos)
    # ----------------------------------------------------------------
    def _get_docs_cobros(self, report_date, branch_id, user_id=False):
        domain = [
            ("payment_type", "=", "inbound"),
            ("state", "in", ["in_process", "paid"]),
        ]
        if report_date:
            domain.append(("date", "=", report_date))
        if branch_id:
            domain.append(("branch_id", "=", branch_id))

        payments = self.env["account.payment"].search(domain, order="name")
        if user_id:
            payments = payments.filtered(
                lambda p: (
                    any(inv.invoice_user_id.id == user_id for inv in p.reconciled_invoice_ids)
                    if not getattr(p, "is_advance", False)
                    else self._advance_belongs_to_user(p, user_id)
                )
            )

        cobros = []
        cobros_anticipos = []
        for pay in payments:
            jname = pay.journal_id.name or "OTROS"
            numero = pay.name or ""
            amount = pay.amount or 0.0
            mode = self._get_payment_mode(pay.journal_id)
            tipo_pago = self._get_payment_mode_label(mode)
            is_advance = getattr(pay, "is_advance", False)
            row = {
                "diario": jname,
                "numero_control": numero,
                "tipo_pago": tipo_pago,
                "total": amount,
            }
            if is_advance:
                cobros_anticipos.append(row)
            else:
                cobros.append(row)

        return cobros, cobros_anticipos

    def _payment_to_anticipo_row(self, pay):
        """Convierte un payment a fila para documento anexo de anticipos."""
        jname = pay.journal_id.name or "OTROS"
        numero = pay.name or ""
        amount = pay.amount or 0.0
        mode = self._get_payment_mode(pay.journal_id)
        tipo_pago = self._get_payment_mode_label(mode)
        return {
            "diario": jname,
            "numero_control": numero,
            "tipo_pago": tipo_pago,
            "total": amount,
        }

    def _get_docs_anticipos_separados(self, docids, data, report_date, branch_id):
        """Devuelve (docs_anticipos_presupuesto, docs_anticipos_prefactura).
        Si data tiene closing_id (reporte desde cierre), usa sus campos.
        Si no, calcula desde report_date/branch_id con la misma lógica.
        """
        closing_id = data.get("closing_id") if data else None
        if closing_id:
            closing = self.env["gn.cash.closing"].browse(closing_id)
            if closing.exists():
                presupuesto = [
                    self._payment_to_anticipo_row(p)
                    for p in closing.advance_presupuesto_ids.sorted("closing_line_sequence")
                ]
                prefactura = [
                    self._payment_to_anticipo_row(p)
                    for p in closing.advance_prefactura_ids.sorted("closing_line_sequence")
                ]
                return presupuesto, prefactura

        # Sin cierre: calcular desde report_date/branch_id
        domain = [
            ("payment_type", "=", "inbound"),
            ("is_advance", "=", True),
            ("state", "in", ["in_process", "paid"]),
            ("date", "=", report_date),
            ("branch_id", "=", branch_id),
        ]
        if "is_advance" not in self.env["account.payment"]._fields:
            return [], []
        advances = self.env["account.payment"].search(domain)
        presupuesto = []
        prefactura = []
        for pay in advances:
            orders = self.env["sale.order"]
            if "sale_order_id" in pay._fields and pay.sale_order_id:
                orders |= pay.sale_order_id
            if "sale_order_advance_link_ids" in pay._fields and pay.sale_order_advance_link_ids:
                orders |= pay.sale_order_advance_link_ids.mapped("sale_order_id")
            row = self._payment_to_anticipo_row(pay)
            if any(o.state == "sale" for o in orders):
                prefactura.append(row)
            else:
                presupuesto.append(row)
        return presupuesto, prefactura

    # ----------------------------------------------------------------
    # DOCUMENTOS ANEXOS - TRASLADOS DE MERCADERIA
    # ----------------------------------------------------------------
    def _get_docs_traslados(self, report_date, branch_id, company=None):
        """Traslados del día considerando zona horaria de la compañía (UTC-6 El Salvador)."""
        domain = [
            ("picking_type_code", "=", "internal"),
            ("state", "=", "done"),
        ]
        if report_date:
            company = company or self.env.company
            start_utc, end_utc = self._get_date_range_utc(report_date, company)
            if start_utc and end_utc:
                domain.append(("scheduled_date", ">=", start_utc))
                domain.append(("scheduled_date", "<", end_utc))
        if branch_id:
            domain.append(("branch_id", "=", branch_id))

        pickings = self.env["stock.picking"].search(domain)

        result = []
        for pick in pickings:
            total_qty = sum(pick.move_ids.mapped("quantity"))
            result.append({
                "description": pick.origin or pick.name,
                "reference": pick.name,
                "uom": "UNIDADES",
                "qty": total_qty,
            })
        return result

    @staticmethod
    def _fmt(value, decimals=2):
        if not value:
            return "0.00"
        return "{:,.{d}f}".format(value, d=decimals)
