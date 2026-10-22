from io import BytesIO

from odoo import models

try:
    import pandas as pd
except ImportError:  # pragma: no cover - optional dependency check
    pd = None


class DynamicReportXlsx(models.AbstractModel):
    _name = "report.custom_dynamic_reports.dynamic_report_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "Dynamic Report XLSX Export"

    def generate_xlsx_report(self, workbook, data, reports):
        header_fmt = workbook.add_format({
            "bold": True,
            "bg_color": "#DEEAF6",
            "border": 1,
        })
        number_fmt = workbook.add_format({"num_format": "#,##0.00"})
        date_fmt = workbook.add_format({"num_format": "yyyy-mm-dd"})

        for report in reports:
            sheet = workbook.add_worksheet(report.name[:31])
            df = report._lines_to_dataframe()
            if df.empty:
                sheet.write(0, 0, "No data available")
                continue

            for col_idx, column in enumerate(df.columns):
                sheet.write(0, col_idx, column, header_fmt)

            for row_idx, (_, row) in enumerate(df.iterrows(), start=1):
                for col_idx, value in enumerate(row):
                    if isinstance(value, float):
                        sheet.write(row_idx, col_idx, value, number_fmt)
                    elif hasattr(value, "isoformat"):
                        sheet.write_datetime(row_idx, col_idx, value, date_fmt)
                    else:
                        sheet.write(row_idx, col_idx, value)

            sheet.autofilter(0, 0, len(df.index), len(df.columns) - 1)
            for col_idx, column in enumerate(df.columns):
                series = df[column].astype(str)
                width = max(series.map(len).max(), len(column)) + 2
                sheet.set_column(col_idx, col_idx, min(width, 75))
