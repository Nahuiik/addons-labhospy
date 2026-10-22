# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, models


class ReportLibroVentasPdf(models.AbstractModel):
    _name = 'report.l10n_hn_account.report_libro_ventas_invoice_view'
    _description = 'Libro de ventas (PDF)'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['libro.ventas.forecast'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'libro.ventas.forecast',
            'docs': docs,
        }
