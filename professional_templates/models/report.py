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


class PDFReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        result = super(PDFReport, self)._render_qweb_pdf(report_ref, res_ids, data)
        report_sudo = self._get_report(report_ref)
        if "professional_templates." not in report_sudo.report_name:
            return result
        if result:
            # watermark & last page uploaded at report level will override the
            # one uploaded at company level
            watermark = (
                report_sudo.pdf_watermark or self.env.company.pdf_watermark or None
            )
            last_page = (
                report_sudo.pdf_last_page or self.env.company.pdf_last_page or None
            )
            if watermark:
                watermark = urlsafe_b64decode(watermark)
            if last_page:
                last_page = urlsafe_b64decode(last_page)
            if not watermark and not last_page:
                return result
            pdf = PdfFileWriter()
            pdf_watermark = None
            if watermark:
                try:
                    pdf_watermark = PdfFileReader(io.BytesIO(watermark))
                    if pdf_watermark.isEncrypted:
                        try:
                            pdf_watermark.decrypt("")
                        except (NotImplementedError, Exception) as e:
                            pdf_watermark = None
                            msg = _(
                                "The uploaded watermark PDF document has security restrictions. Can not read or decrypt it!: "
                            )
                            msg += str(e)
                            LOGGER.warning(msg)
                            raise UserError(msg)
                except PdfReadError:
                    try:
                        image = Image.open(io.BytesIO(watermark))
                        pdf_buffer = io.BytesIO()
                        if image.mode != "RGB":
                            image = image.convert("RGB")
                        resolution = image.info.get(
                            "dpi", report_sudo.paperformat_id.dpi or 90
                        )
                        if isinstance(resolution, tuple):
                            resolution = resolution[0]
                        # save the image as PDF
                        image.save(pdf_buffer, "pdf", resolution=resolution)
                        pdf_watermark = PdfFileReader(pdf_buffer)
                    except BaseException:
                        msg = _("Failed to load the non PDF watermark...")
                        LOGGER.exception(msg)
                if not pdf_watermark:
                    msg = _("No usable watermark found, got ")
                    LOGGER.info(msg + " %s", watermark[:100])

            if pdf_watermark and pdf_watermark.numPages < 1:
                msg = _(
                    "Your watermark pdf does not contain a page or is not a standard PDF document"
                )
                LOGGER.info(msg)
                return result
            if pdf_watermark and pdf_watermark.numPages > 1:
                msg = _(
                    "Your watermark pdf contains more than one page. Only the first page will be used!"
                )
                LOGGER.info(msg)
            doc = PdfFileReader(io.BytesIO(result[0]))
            if pdf_watermark:
                for page in doc.pages:
                    watermark_page = pdf.addBlankPage(
                        page.mediaBox.getWidth(), page.mediaBox.getHeight()
                    )
                    # Use the first page of the watermark PDF only
                    watermark_page.mergePage(pdf_watermark.getPage(0))
                    watermark_page.mergePage(page)
            if last_page:
                pdf_last_page = PdfFileReader(io.BytesIO(last_page))
                if pdf_last_page.isEncrypted:
                    try:
                        pdf_last_page.decrypt("")
                    except (NotImplementedError, Exception) as e:
                        pdf_last_page = None
                        msg = _(
                            "The Last Page PDF document has security restrictions. Can not read or decrypt it!: "
                        )
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


class ReportInvoiceWithoutPayment(models.AbstractModel):
    _name = "report.professional_templates.report_invoice"
    _description = "Account report without payment lines"
    _inherit = "report.account.report_invoice"

    @api.model
    def _get_report_values(self, docids, data=None):
        return super()._get_report_values(docids, data)


class ReportInvoiceWithPayment(models.AbstractModel):
    _name = "report.professional_templates.report_invoice_with_payments"
    _description = "Account report with payment lines"
    _inherit = "report.professional_templates.report_invoice"

    @api.model
    def _get_report_values(self, docids, data=None):
        return super()._get_report_values(docids, data)
