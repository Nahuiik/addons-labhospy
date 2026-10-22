# -*- coding: utf-8 -*-
"""Logo para QWeb: mismas fuentes que report_branding (no solo logo_web)."""
import base64
import logging

from odoo import http
from odoo.http import request
from odoo.tools.mimetypes import guess_mimetype

from odoo.addons.l10n_hn_reports.models import report_branding as rb

_logger = logging.getLogger(__name__)


class HnReportLogoController(http.Controller):
    @http.route(
        '/web/binary/hn_company_report_logo',
        type='http',
        auth='public',
        cors='*',
        readonly=True,
    )
    def hn_company_report_logo(self, company=None, **kw):
        """Sirve logo de la compañía (logo_web, logo, imagen del contacto)."""
        try:
            cid = int(company) if company else 0
        except (TypeError, ValueError):
            cid = 0
        if not request.db or not cid:
            return request.not_found()
        comp = request.env['res.company'].sudo().browse(cid)
        if not comp.exists():
            return request.not_found()

        logo_b64 = None
        for field_name in ('logo_web', 'logo'):
            logo_b64 = rb._logo_field_to_b64(getattr(comp, field_name, None))
            if logo_b64:
                break
        if not logo_b64 and comp.partner_id:
            logo_b64 = rb._logo_field_to_b64(comp.partner_id.sudo().image_1920)
        if not logo_b64:
            return request.redirect('/web/static/img/nologo.png')
        try:
            raw = base64.b64decode(''.join(logo_b64.split()))
        except Exception:
            _logger.debug('hn_company_report_logo: base64 inválido company=%s', cid, exc_info=True)
            return request.redirect('/web/static/img/nologo.png')
        if not raw:
            return request.redirect('/web/static/img/nologo.png')
        mimetype = guess_mimetype(raw, default='image/png')
        headers = [
            ('Content-Type', mimetype),
            ('Cache-Control', 'private, max-age=3600'),
        ]
        return request.make_response(raw, headers=headers)
