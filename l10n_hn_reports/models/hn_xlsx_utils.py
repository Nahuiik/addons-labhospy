# -*- coding: utf-8 -*-
"""Cálculo de anchos de columna para informes XLSX (xlsxwriter no tiene autofit nativo)."""


def hn_xlsx_str_width(value, float_decimals=2):
    """Ancho textual aproximado (equiv. Excel autofit sin fuente proporcional ni CJK amplio)."""
    if value is None:
        return 0
    if isinstance(value, float):
        decimals = max(0, min(15, int(float_decimals)))
        fmt = '{{:,.{n}f}}'.format(n=decimals)
        try:
            return len(fmt.format(value))
        except (ValueError, OverflowError):
            return len(str(value))
    if isinstance(value, bool):
        return len('TRUE' if value else 'FALSE')
    if isinstance(value, int):
        return len(str(value))
    return len(str(value))


def hn_xlsx_columns_widths(
        table_rows,
        min_width=10,
        max_width=78,
        padding=2,
        column_float_decimals=None,
):
    """Devuelve un ancho por columna según la celda más ancha por columna (cabeceras + datos)."""
    if not table_rows:
        return []
    ncols = max((len(row) for row in table_rows), default=0)
    widths = []
    for col in range(ncols):
        dec = 2
        if column_float_decimals and col in column_float_decimals:
            dec = column_float_decimals[col]
        maxlen = min_width
        for row in table_rows:
            if col < len(row):
                maxlen = max(maxlen, hn_xlsx_str_width(row[col], float_decimals=dec))
        widths.append(min(max_width, maxlen + padding))
    return widths


def hn_xlsx_apply_column_widths(sheet, table_rows, first_col=0, **kwargs):
    """Aplica ``set_column`` según contenido — xlsxwriter no ofrece autofit nativo."""
    kw = dict(kwargs)
    column_float_decimals = kw.pop('column_float_decimals', None)
    for offset, width in enumerate(
            hn_xlsx_columns_widths(
                table_rows,
                column_float_decimals=column_float_decimals,
                **kw,
            )):
        c = first_col + offset
        sheet.set_column(c, c, width)
