# -*- coding: utf-8 -*-

from odoo import _, models

NCOLS = 11


def _gn_xlsx_str_width(value, float_decimals=2):
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
    return len(str(value).replace('\n', ' '))


def _gn_xlsx_columns_widths(table_rows, min_width=10, max_width=55, padding=3):
    if not table_rows:
        return []
    ncols = max((len(row) for row in table_rows), default=NCOLS)
    widths = []
    for col in range(ncols):
        maxlen = min_width
        for row in table_rows:
            if col < len(row):
                maxlen = max(
                    maxlen,
                    _gn_xlsx_str_width(row[col], float_decimals=2),
                )
        widths.append(min(max_width, maxlen + padding))
    return widths


class ReportGnLabhospyControlledSubstancesXlsx(models.AbstractModel):
    _name = 'report.gn_labhospy.controlled_substances_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'XLSX sustancias controladas'

    def _xlsx_formats(self, workbook):
        return {
            'title': workbook.add_format({
                'bold': True,
                'font_size': 16,
                'align': 'center',
                'valign': 'vcenter',
                'bottom': 2,
            }),
            'meta_label': workbook.add_format({
                'bold': True,
                'font_size': 12,
                'valign': 'top',
                'text_wrap': True,
                'bg_color': '#f7fafc',
                'border': 1,
            }),
            'meta_value': workbook.add_format({
                'font_size': 12,
                'valign': 'top',
                'text_wrap': True,
                'bg_color': '#f7fafc',
                'border': 1,
            }),
            'prod_code': workbook.add_format({
                'bold': True,
                'font_size': 12,
                'align': 'left',
                'valign': 'vcenter',
                'text_wrap': True,
                'bg_color': '#edf2f7',
                'border': 1,
            }),
            'prod_name': workbook.add_format({
                'bold': True,
                'font_size': 12,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
                'bg_color': '#edf2f7',
                'border': 1,
            }),
            'prod_cat': workbook.add_format({
                'bold': True,
                'font_size': 12,
                'align': 'right',
                'valign': 'vcenter',
                'text_wrap': True,
                'bg_color': '#edf2f7',
                'border': 1,
            }),
            'head': workbook.add_format({
                'bold': True,
                'font_size': 12,
                'bg_color': '#2d3748',
                'font_color': '#ffffff',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
            }),
            'head_num': workbook.add_format({
                'bold': True,
                'font_size': 12,
                'bg_color': '#2d3748',
                'font_color': '#ffffff',
                'border': 1,
                'align': 'right',
                'valign': 'vcenter',
                'text_wrap': True,
            }),
            'cell': workbook.add_format({
                'font_size': 12,
                'border': 1,
                'align': 'left',
                'valign': 'top',
                'text_wrap': True,
            }),
            'cell_initial': workbook.add_format({
                'font_size': 12,
                'border': 1,
                'align': 'left',
                'valign': 'top',
                'text_wrap': True,
                'bold': True,
                'bg_color': '#e2e8f0',
            }),
            'num': workbook.add_format({
                'font_size': 12,
                'border': 1,
                'align': 'right',
                'valign': 'vcenter',
                'num_format': '#,##0.00',
            }),
            'num_initial': workbook.add_format({
                'font_size': 12,
                'border': 1,
                'align': 'right',
                'valign': 'vcenter',
                'num_format': '#,##0.00',
                'bold': True,
                'bg_color': '#e2e8f0',
            }),
        }

    def _write_meta_row(self, sheet, row, label, value, fmt_label, fmt_value):
        sheet.merge_range(row, 0, row, 1, label, fmt_label)
        sheet.merge_range(row, 2, row, NCOLS - 1, value or '', fmt_value)
        return row + 1

    def generate_xlsx_report(self, workbook, data, wizards):
        fmt = self._xlsx_formats(workbook)
        headers = [
            _('Fecha'),
            _('Empresa a quien es vendida'),
            _('Dirección'),
            _('Aplicación / uso'),
            _('Transacción'),
            _('Resolución'),
            _('Documento'),
            _('Lote'),
            _('Ingreso'),
            _('Salida'),
            _('Saldo'),
        ]

        for wiz in wizards:
            pages = wiz._build_ledger_sections()
            company = wiz.company_id
            period_label = '%s — %s' % (
                wiz._format_sc_report_date(wiz.date_from),
                wiz._format_sc_report_date(wiz.date_to),
            )

            sheet = workbook.add_worksheet(_('Sustancias controladas')[:31])
            sheet.set_landscape()
            sheet.set_paper(9)  # A4
            sheet.hide_gridlines(2)

            autofit_rows = [headers]
            r = 0

            sheet.merge_range(r, 0, r, NCOLS - 1, _('Venta de Sustancias Químicas Controladas'), fmt['title'])
            sheet.set_row(r, 28)
            r += 1

            r = self._write_meta_row(
                sheet, r,
                _('Compañía:'),
                company.name,
                fmt['meta_label'], fmt['meta_value'],
            )
            r = self._write_meta_row(
                sheet, r,
                _('Período consultado:'),
                period_label,
                fmt['meta_label'], fmt['meta_value'],
            )
            r += 1

            if not pages:
                sheet.merge_range(
                    r, 0, r, NCOLS - 1,
                    _('No hay movimientos de sustancias controladas en el período seleccionado.'),
                    fmt['cell'],
                )
                continue

            for page in pages:
                r += 1
                sheet.set_row(r, 6)
                r += 1

                meta_lines = [
                    (_('Nombre del establecimiento:'), page.get('establishment_name') or company.name),
                    (_('Sucursal:'), page.get('branch_name') or ''),
                    (_('No. licencia sanitaria:'), page.get('license_no') or ''),
                    (_('Teléfono:'), page.get('phone') or ''),
                    (_('Período consultado:'), period_label),
                    (_('Dirección principal:'), page.get('address') or ''),
                ]
                for label, value in meta_lines:
                    if not value and label != _('Nombre del establecimiento:'):
                        continue
                    r = self._write_meta_row(sheet, r, label, value, fmt['meta_label'], fmt['meta_value'])
                    sheet.set_row(r - 1, 18)

                catalog = ''
                if page.get('hdr_catalog'):
                    catalog = '%s: %s' % (
                        page.get('catalog_label') or _('Catálogo'),
                        page['hdr_catalog'],
                    )

                sheet.write(r, 0, page.get('hdr_code') or '', fmt['prod_code'])
                sheet.merge_range(r, 1, r, 7, page.get('hdr_name') or '', fmt['prod_name'])
                sheet.merge_range(r, 8, r, NCOLS - 1, catalog, fmt['prod_cat'])
                sheet.set_row(r, 22)
                r += 1

                for c, lab in enumerate(headers):
                    head_fmt = fmt['head_num'] if c >= 8 else fmt['head']
                    sheet.write(r, c, lab, head_fmt)
                sheet.set_row(r, 24)
                r += 1

                for data_row in page.get('rows', []):
                    is_initial = data_row.get('es_saldo_inicial')
                    cell_fmt = fmt['cell_initial'] if is_initial else fmt['cell']
                    num_fmt = fmt['num_initial'] if is_initial else fmt['num']

                    ing = data_row.get('ingreso')
                    sal = data_row.get('salida')
                    sld = data_row.get('saldo')

                    line_vals = [
                        data_row.get('fecha_str') or '',
                        data_row.get('empresa_contacto') or '',
                        data_row.get('direccion') or '',
                        data_row.get('aplicacion_uso') or '',
                        data_row.get('transaccion') or '',
                        data_row.get('resolucion') or '',
                        data_row.get('documento') or '',
                        data_row.get('lote') or '',
                        ing if ing != '' else None,
                        sal if sal != '' else None,
                        sld if sld != '' and sld is not None else None,
                    ]
                    autofit_rows.append(line_vals)

                    for c, val in enumerate(line_vals):
                        if c >= 8:
                            if val is not None and val != '':
                                sheet.write(r, c, float(val), num_fmt)
                            else:
                                sheet.write(r, c, '', num_fmt)
                        else:
                            sheet.write(r, c, val or '', cell_fmt)

                    lines = max(
                        (val or '').count('\n') + 1
                        for val in line_vals[:8]
                        if isinstance(val, str)
                    )
                    sheet.set_row(r, max(18, min(60, 16 * lines)))
                    r += 1

            widths = _gn_xlsx_columns_widths(autofit_rows)
            default_widths = [11, 28, 24, 20, 18, 12, 16, 12, 10, 10, 10]
            for i in range(NCOLS):
                w = widths[i] if i < len(widths) else default_widths[i]
                sheet.set_column(i, i, max(w, default_widths[i]))
