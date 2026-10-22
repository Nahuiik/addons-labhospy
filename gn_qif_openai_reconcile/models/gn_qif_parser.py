# -*- coding: utf-8 -*-
"""Parser QIF (Community, sin Enterprise)."""
import io
import logging

import dateutil.parser
from odoo import _
from odoo.exceptions import UserError

logger = logging.getLogger(__name__)

QIF_DATE = b'D'
QIF_AMOUNT = b'T'
QIF_CHECK = b'N'
QIF_PAYEE = b'P'
QIF_MEMO = b'M'
QIF_END = b'^'


def _decode_line(data: bytes) -> str:
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        return data.decode('latin-1')


def parse_qif_bytes(journal, raw_bytes: bytes):
    """Parsea un archivo QIF.

    :param journal: recordset `account.journal` (puede estar vacío)
    :return: (transactions, metadata)
    """
    if not (raw_bytes or b'').strip().startswith(b'!Type:'):
        raise UserError(_('El archivo no es un QIF válido.'))

    data_list = [l.rstrip(b'\r\n') for l in io.BytesIO(raw_bytes.strip())]
    try:
        header = data_list[0].strip().split(b':')[1]
    except IndexError:
        raise UserError(_('No se pudo leer la cabecera del archivo QIF.'))
    if header not in (b'Bank', b'Cash', b'CCard'):
        raise UserError(_('Tipo QIF no soportado: %s') % _decode_line(header))

    if journal:
        dayfirst = getattr(journal, 'qif_date_format', 'day_first') == 'day_first'
        decimal_point = getattr(journal, 'qif_decimal_point', '.') or '.'
    else:
        dayfirst = True
        decimal_point = '.'

    transactions = []
    current = {'payment_ref': []}
    total_amount = 0.0
    dates = []
    for line in data_list:
        line = line.strip()
        if not line:
            continue
        tag, data = line[:1], line[1:]
        if tag == QIF_DATE:
            current['date'] = dateutil.parser.parse(data, fuzzy=True, dayfirst=dayfirst).date()
        elif tag == QIF_AMOUNT:
            amount = float(data.replace(b',', b'.' if decimal_point == ',' else b''))
            current['amount'] = amount
            total_amount += amount
        elif tag == QIF_CHECK:
            current['ref'] = _decode_line(data)
        elif tag == QIF_PAYEE:
            current['payment_ref'].append(_decode_line(data))
        elif tag == QIF_MEMO:
            current['payment_ref'].append(_decode_line(data))
        elif tag == QIF_END:
            current['sequence'] = len(transactions) + 1
            current['payment_ref'] = ': '.join(current['payment_ref']) if current['payment_ref'] else ''
            if current.get('date'):
                dates.append(current['date'])
            transactions.append(current)
            current = {'payment_ref': []}

    metadata = {
        'min_date': min(dates) if dates else None,
        'max_date': max(dates) if dates else None,
        'total_amount': total_amount,
        'count': len(transactions),
    }
    return transactions, metadata
