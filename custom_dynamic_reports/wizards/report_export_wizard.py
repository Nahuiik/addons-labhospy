import base64

from odoo import _, fields, models


class DynamicReportExportWizard(models.TransientModel):
    _name = "dynamic.report.export.wizard"
    _description = "Dynamic Report Export Wizard"

    report_id = fields.Many2one("dynamic.report", required=True, ondelete="cascade")
    export_format = fields.Selection([
        ("xlsx", "Excel (.xlsx)"),
        ("pdf", "PDF"),
    ], default="xlsx", required=True)
    file_data = fields.Binary(readonly=True)
    file_name = fields.Char(readonly=True)

    def action_export(self):
        self.ensure_one()
        if self.export_format == "xlsx":
            data = self.report_id._export_xlsx_bytes()
            filename = f"{self.report_id.name or 'report'}.xlsx"
            self.write({
                "file_data": base64.b64encode(data),
                "file_name": filename,
            })
            return {
                "type": "ir.actions.act_url",
                "url": (
                    "/web/content/?model=dynamic.report.export.wizard&"
                    f"id={self.id}&field=file_data&filename_field=file_name&download=true"
                ),
                "target": "self",
            }

        return self.report_id._get_report_action_pdf()
