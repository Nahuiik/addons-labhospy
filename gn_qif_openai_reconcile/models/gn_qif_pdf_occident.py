# -*- coding: utf-8 -*-
"""Extracción de movimientos de estados de cuenta PDF (ej. Banco de Occidente HN).

El layout del PDF de Occidente, al extraer texto con pypdf, usa bloques línea a línea:
fecha DD-MM-YYYY, hora, agencia, cajero, trx, referencia, descripción (opcionalmente
multilínea), débito, crédito, saldo. El pie del documento trae cuenta, titular,
moneda (LPS) y saldos inicial/final.
"""
from __future__ import annotations

import io
import logging
import re
from datetime import datetime

from odoo import _
from odoo.exceptions import UserError

logger = logging.getLogger(__name__)

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

DATE_LINE = re.compile(r"^(\d{2})-(\d{2})-(\d{4})$")
TIME_LINE = re.compile(r"^\d{2}:\d{2}:\d{2}$")
FOOTER_SPLIT = "Resumen de Movimientos"

def extract_pdf_plain_text(raw_bytes: bytes) -> str:
    if not raw_bytes or not raw_bytes.strip():
        raise UserError(_("El archivo PDF está vacío."))
    if PdfReader is None:
        raise UserError(
            _(
                "Falta la librería Python «pypdf». Instálala en el mismo entorno que Odoo "
                "(pip install pypdf) y reinicie."
            )
        )
    reader = PdfReader(io.BytesIO(raw_bytes))
    parts = []
    for page in reader.pages:
        t = page.extract_text() or ""
        parts.append(t)
    full = "\n".join(parts)
    if not full.strip():
        raise UserError(_("No se pudo extraer texto del PDF (¿escaneado sin OCR?)."))
    return full


def _parse_amount_hn(s: str) -> float:
    s = (s or "").strip().replace(",", "").replace(" ", "")
    if not s or s.upper() == "N/D":
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_footer_meta(full_text: str) -> dict:
    """Extrae metadatos del bloque típico de Occidente (cuenta, titular, moneda, saldos)."""
    meta = {
        "account_number": "",
        "titular": "",
        "currency": "",
        "balance_start": 0.0,
        "balance_end": 0.0,
    }
    blob = full_text.replace("\x00", " ")
    mm = re.search(r"Cuenta:\s*([\d\-]+)", blob, re.M)
    if mm:
        meta["account_number"] = mm.group(1).strip()
    # línea siguiente al número de cuenta suele ser el nombre
    mlines = blob.splitlines()
    for i, ln in enumerate(mlines):
        if ln.strip().startswith("Cuenta:") and i + 1 < len(mlines):
            cand = (mlines[i + 1] or "").strip()
            if cand and not cand.startswith("Producto"):
                meta["titular"] = cand[:256]
                break
    mp = re.search(r"Producto:\s*([^\n]+)", blob, re.I)
    if mp and "titular" not in meta or not meta.get("titular"):
        pass  # opcional producto CUENTA DE CHEQUES…
    mcur = re.search(r"Moneda:\s*([A-Za-z]{2,6})", blob, re.I)
    if mcur:
        cur = mcur.group(1).strip().upper()
        if cur == "LPS":
            cur = "HNL"
        meta["currency"] = cur
    mins = re.search(r"Saldo\s+Inicial:\s*([\d,\.]+)", blob, re.I)
    mend = re.search(r"Saldo\s+Final:\s*([\d,\.]+)", blob, re.I)
    if mins:
        meta["balance_start"] = _parse_amount_hn(mins.group(1))
    if mend:
        meta["balance_end"] = _parse_amount_hn(mend.group(1))
    return meta


def _truncate_duplicate_summary(slab: list[str]) -> list[str]:
    """Quita tabla resumen repetida («Descripción / N° Trans.») pegada al último movimiento."""
    for i in range(max(0, len(slab) - 1)):
        if slab[i] == "Descripción" and i + 1 < len(slab) and "Trans" in slab[i + 1]:
            return slab[:i]
    return slab


def _transaction_section_lines(full_text: str) -> list[str]:
    """Recorta texto hasta antes del resumen de movimientos (tabla inferior)."""
    if FOOTER_SPLIT in full_text:
        full_text = full_text.split(FOOTER_SPLIT)[0]
    lines = []
    seen_header = False
    for ln in full_text.replace("\r\n", "\n").split("\n"):
        s = ln.strip()
        if not s:
            continue
        ul = " ".join(s.split())
        if ul.startswith("Descripción Debito Credito Saldo"):
            seen_header = True
            continue
        if ul.startswith(("Fecha Hora ", "Estado de Cuenta")):
            continue
        if not seen_header and ul.startswith(("Fecha", "Hora", "Debito")):
            continue
        lines.append(s)
    return lines


def _date_indices(lines: list[str]) -> list[int]:
    idxs = []
    for i, s in enumerate(lines):
        if not DATE_LINE.match(s):
            continue
        # Evita falsos positivos del pie (tablas sin hora después de fecha)
        if i + 1 < len(lines) and TIME_LINE.match(lines[i + 1]):
            idxs.append(i)
    return idxs


def _looks_like_money(s: str) -> bool:
    t = (s or "").strip().replace(",", "").replace(" ", "")
    if not t:
        return False
    if t.upper() in ("N/D",):
        return True
    try:
        float(t)
        return True
    except ValueError:
        return False


def _parse_occident_slab(slab: list[str], seq: int) -> dict | None:
    """Un bloque línea fecha .. débito crédito saldo."""
    if len(slab) < 10:
        return None
    m = DATE_LINE.match(slab[0])
    if not m:
        return None
    try:
        dt_val = datetime.strptime(slab[0], "%d-%m-%Y").date()
    except ValueError:
        return None
    # time, agency, cashier, trx
    i = 5
    ref = slab[i] if i < len(slab) else ""
    i += 1
    descr_parts = []
    while i < len(slab) - 3:
        line = slab[i]
        if DATE_LINE.match(line):
            return None  # inconsistencia / bloque incompleto
        descr_parts.append(line)
        i += 1
    if len(slab) - i != 3:
        return None
    debit_str, credit_str, saldo_str = slab[-3], slab[-2], slab[-1]
    if not all(_looks_like_money(x) for x in (debit_str, credit_str, saldo_str)):
        return None
    debit = _parse_amount_hn(debit_str)
    credit = _parse_amount_hn(credit_str)
    amount = credit - debit
    desc = " ".join(descr_parts)
    desc = re.sub(r"\s+", " ", desc).strip() or _("Sin descripción")
    return {
        "date": dt_val,
        "amount": amount,
        "payment_ref": desc[:2048],
        "ref": (ref or "")[:256],
        "sequence": seq,
    }


def parse_occidente_statement_from_text(full_text: str) -> tuple[list, dict]:
    """Parse texto extraído de PDF Occident-style → (transactions, metadata)."""
    footer = _parse_footer_meta(full_text)
    raw_lines = _transaction_section_lines(full_text)
    idxs = _date_indices(raw_lines)
    transactions: list[dict] = []
    for j, pos in enumerate(idxs):
        end = idxs[j + 1] if j + 1 < len(idxs) else len(raw_lines)
        slab = _truncate_duplicate_summary(raw_lines[pos:end])
        parsed = _parse_occident_slab(slab, len(transactions) + 1)
        if parsed:
            transactions.append(parsed)
        else:
            logger.debug("omitido slab en posición PDF %s: %s", pos, slab[:12])

    if not transactions:
        raise UserError(
            _(
                "No se encontraron movimientos en el PDF en el formato Banco Occidente "
                "(fecha DD-MM-YYYY con columnas débito/crédito/saldo). Si el archivo es una "
                "imagen escaneada, OCR no está disponible en este importador."
            )
        )

    dates = [t["date"] for t in transactions if t.get("date")]
    total_amount = sum(t.get("amount", 0.0) for t in transactions)
    meta = {
        "min_date": min(dates) if dates else None,
        "max_date": max(dates) if dates else None,
        "total_amount": total_amount,
        "count": len(transactions),
        "balance_start": footer.get("balance_start", 0.0),
        "balance_end": footer.get("balance_end", 0.0),
        "titular": footer.get("titular", ""),
        "account_number": footer.get("account_number", ""),
        "bank_name": _("PDF Estado de cuenta (layout tipo Banco de Occidente, HN)"),
        "currency": footer.get("currency", "HNL"),
    }
    return transactions, meta
