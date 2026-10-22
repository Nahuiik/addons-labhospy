# -*- coding: utf-8 -*-
# Part of l10n_hn_stock. See LICENSE file for full copyright and licensing details.

import io
import logging
from base64 import urlsafe_b64decode

from PIL import Image
from PyPDF2 import PdfFileReader, PdfFileWriter

from odoo import _, models
from odoo.exceptions import UserError

try:
    from PyPDF2.errors import PdfReadError
except ImportError:
    from PyPDF2.utils import PdfReadError

_LOGGER = logging.getLogger(__name__)

REMISSION_INTER_STORE_REPORT = "l10n_hn_stock.report_remission_inter_store_template"
INTER_STORE_TRANSFER_MODEL = "stock.inter.store.transfer"


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _l10n_hn_inter_store_docs_for_report(self, docs):
        """Permite leer sucursales origen/destino en el PDF si el usuario puede leer el traslado.

        La record rule de res.branch limita a user.branch_ids; en traslados entre tiendas
        el usuario de una sucursal necesita ver el nombre/CAI de la otra al imprimir.
        """
        if not docs:
            return docs
        docs.check_access("read")
        return docs.sudo()

    def _get_rendering_context(self, report, docids, data):
        data = super()._get_rendering_context(report, docids, data)
        if report.model == INTER_STORE_TRANSFER_MODEL and data.get("docs") is not None:
            data["docs"] = self._l10n_hn_inter_store_docs_for_report(data["docs"])
        return data

    def _l10n_hn_merge_remission_watermark(self, pdf_bytes, watermark_raw, report_sudo):
        """Fusiona la primera página de plantilla bajo el contenido (misma lógica que GTS)."""
        pdf = PdfFileWriter()
        pdf_watermark = None
        try:
            pdf_watermark = PdfFileReader(io.BytesIO(watermark_raw))
            if pdf_watermark.isEncrypted:
                try:
                    pdf_watermark.decrypt("")
                except (NotImplementedError, Exception) as e:
                    pdf_watermark = None
                    msg = _("El PDF de plantilla tiene restricciones de seguridad: %s") % (e,)
                    _LOGGER.warning(msg)
                    raise UserError(msg) from e
        except PdfReadError:
            try:
                image = Image.open(io.BytesIO(watermark_raw))
                pdf_buffer = io.BytesIO()
                if image.mode != "RGB":
                    image = image.convert("RGB")
                resolution = image.info.get("dpi", report_sudo.paperformat_id.dpi or 90)
                if isinstance(resolution, tuple):
                    resolution = resolution[0]
                image.save(pdf_buffer, "pdf", resolution=resolution)
                pdf_watermark = PdfFileReader(pdf_buffer)
            except Exception as e:  # noqa: BLE001
                _LOGGER.exception("l10n_hn_stock: plantilla guía remisión")
                raise UserError(_("No se pudo cargar la plantilla PDF o imagen.")) from e

        if not pdf_watermark or pdf_watermark.numPages < 1:
            return pdf_bytes

        doc = PdfFileReader(io.BytesIO(pdf_bytes))
        for page in doc.pages:
            watermark_page = pdf.addBlankPage(page.mediaBox.getWidth(), page.mediaBox.getHeight())
            watermark_page.mergePage(pdf_watermark.getPage(0))
            watermark_page.mergePage(page)
        out = io.BytesIO()
        pdf.write(out)
        return out.getvalue()

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        result = super()._render_qweb_pdf(report_ref, res_ids, data)
        report_sudo = self._get_report(report_ref)
        if report_sudo.report_name != REMISSION_INTER_STORE_REPORT or not result:
            return result
        if not res_ids:
            return result
        transfer = self.env[INTER_STORE_TRANSFER_MODEL].browse(res_ids[0])
        transfer.check_access("read")
        # Marca de agua de la sucursal origen: el usuario destino puede no tenerla en branch_ids.
        branch = transfer.sudo().branch_id
        if not branch or not branch.pdf_watermark_branch_remission:
            return result
        watermark_raw = urlsafe_b64decode(branch.pdf_watermark_branch_remission)
        merged = self._l10n_hn_merge_remission_watermark(
            result[0],
            watermark_raw,
            report_sudo,
        )
        return merged, "pdf"
