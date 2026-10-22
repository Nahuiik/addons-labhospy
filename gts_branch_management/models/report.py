# -*- coding: utf-8 -*-
"""
Odoo Proprietary License v1.0.

see License:
https://www.odoo.com/documentation/user/17.0/legal/licenses/licenses.html#odoo-apps
# Copyright ©2023 Bernard K. Too<bernard.too@optima.co.ke>
"""
import io
from base64 import urlsafe_b64decode
from logging import getLogger

from PIL import Image
from PyPDF2 import PdfFileReader, PdfFileWriter

from odoo import _, api, models
from odoo.exceptions import UserError

try:
    from PyPDF2.errors import PdfReadError
except ImportError:
    from PyPDF2.utils import PdfReadError


LOGGER = getLogger(__name__)

# Reportes QWeb (fuera de professional_templates) que deben recibir watermark / última página de sucursal o compañía.
BRANCH_PDF_EXTRA_REPORT_NAMES = frozenset({
    "l10n_hn_stock.report_remission_template",
})


class PDFReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        result = super(PDFReport, self)._render_qweb_pdf(report_ref, res_ids, data)
        report_sudo = self._get_report(report_ref)

        report_name = report_sudo.report_name or ""
        if (
            "professional_templates." not in report_name
            and report_name not in BRANCH_PDF_EXTRA_REPORT_NAMES
        ):
            return result

        if result:
            # Obtener sucursal del usuario
            branch = self.env.user.branch_id

            # Elegir watermark según prioridad: sucursal > reporte > compañía
            watermark = None
            if report_sudo.model == 'account.move' or report_sudo.model == 'account.payment' and branch:
                watermark = branch.pdf_watermark_branch
            elif report_sudo.model == 'sale.order' or report_sudo.model == 'purchase.order' or report_sudo.model == 'stock.picking' and branch:
                watermark = branch.pdf_watermark_branch_order

            watermark = watermark or report_sudo.pdf_watermark or self.env.company.pdf_watermark or None
            last_page = report_sudo.pdf_last_page or self.env.company.pdf_last_page or None

            if watermark:
                watermark = urlsafe_b64decode(watermark)
            if last_page:
                last_page = urlsafe_b64decode(last_page)

            if not watermark and not last_page:
                return result

            pdf = PdfFileWriter()
            pdf_watermark = None

            # Procesar el watermark
            if watermark:
                try:
                    pdf_watermark = PdfFileReader(io.BytesIO(watermark))
                    if pdf_watermark.isEncrypted:
                        try:
                            pdf_watermark.decrypt("")
                        except (NotImplementedError, Exception) as e:
                            pdf_watermark = None
                            msg = _("The uploaded watermark PDF document has security restrictions. Can not read or decrypt it!: ")
                            msg += str(e)
                            LOGGER.warning(msg)
                            raise UserError(msg)
                except PdfReadError:
                    try:
                        image = Image.open(io.BytesIO(watermark))
                        pdf_buffer = io.BytesIO()
                        if image.mode != "RGB":
                            image = image.convert("RGB")
                        resolution = image.info.get("dpi", report_sudo.paperformat_id.dpi or 90)
                        if isinstance(resolution, tuple):
                            resolution = resolution[0]
                        image.save(pdf_buffer, "pdf", resolution=resolution)
                        pdf_watermark = PdfFileReader(pdf_buffer)
                    except BaseException:
                        msg = _("Failed to load the non PDF watermark...")
                        LOGGER.exception(msg)

                if not pdf_watermark:
                    msg = _("No usable watermark found, got ")
                    LOGGER.info(msg + " %s", watermark[:100])

            if pdf_watermark and pdf_watermark.numPages < 1:
                msg = _("Your watermark pdf does not contain a page or is not a standard PDF document")
                LOGGER.info(msg)
                return result
            if pdf_watermark and pdf_watermark.numPages > 1:
                msg = _("Your watermark pdf contains more than one page. Only the first page will be used!")
                LOGGER.info(msg)

            doc = PdfFileReader(io.BytesIO(result[0]))

            if pdf_watermark:
                for page in doc.pages:
                    watermark_page = pdf.addBlankPage(page.mediaBox.getWidth(), page.mediaBox.getHeight())
                    watermark_page.mergePage(pdf_watermark.getPage(0))
                    watermark_page.mergePage(page)

            if last_page:
                pdf_last_page = PdfFileReader(io.BytesIO(last_page))
                if pdf_last_page.isEncrypted:
                    try:
                        pdf_last_page.decrypt("")
                    except (NotImplementedError, Exception) as e:
                        pdf_last_page = None
                        msg = _("The Last Page PDF document has security restrictions. Can not read or decrypt it!: ")
                        msg += str(e)
                        LOGGER.warning(msg)
                        raise UserError(msg)

                if not pdf_watermark:
                    for page in doc.pages:
                        pdf.addPage(page)

                if pdf_last_page:
                    for last in pdf_last_page.pages:
                        pdf.addPage(last)

            result = io.BytesIO()
            pdf.write(result)
            return result.getvalue(), "pdf"

        return result
