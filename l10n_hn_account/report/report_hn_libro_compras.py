# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, models


class ReportLibroComprasPdf(models.AbstractModel):
    _name = 'report.l10n_hn_account.report_libro_compras_invoice_view'
    _description = 'Libro de compras (PDF)'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['libro.compras.forecast'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'libro.compras.forecast',
            'docs': docs,
        }
