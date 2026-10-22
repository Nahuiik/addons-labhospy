# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# License: LGPL-3

import time

from odoo import api, fields, models


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    _HN_VACATION_LEAVE_QWEB_REPORTS = frozenset({
        'l10n_hn_hr_payroll.report_hn_vacation_constancia',
        'l10n_hn_hr_payroll.report_hn_vacation_solicitud',
        'l10n_hn_hr_payroll.report_hn_vacation_preaviso',
    })

    def _get_rendering_context(self, report, docids, data):
        """Los PDF de vacaciones HN deben leer hr.leave aunque la empresa activa no sea la del ausente."""
        ctx = super()._get_rendering_context(report, docids, data)
        if (
            report.report_name in self._HN_VACATION_LEAVE_QWEB_REPORTS
            and report.model == 'hr.leave'
        ):
            docs = ctx.get('docs')
            if docs is not None and docs._name == 'hr.leave':
                ctx = dict(ctx)
                ctx['docs'] = docs.sudo()
        return ctx

    ICP_PDF_LOOPBACK = 'report.pdf.use_loopback_assets'

    @api.model
    def _report_pdf_internal_base_url(self):
        """Base URL que el proceso wkhtmltopdf puede abrir en este servidor."""
        from odoo.tools import config

        port = config.get('http_port') or 8069
        interface = config.get('http_interface')
        if not interface or interface in ('0.0.0.0', '::'):
            host = '127.0.0.1'
        else:
            host = interface
        return f'http://{host}:{port}'

    @api.model
    def _get_report_base_for_pdf_assets(self):
        """URL para enlaces a /web/assets en HTML de informes PDF."""
        icp = self.env['ir.config_parameter'].sudo()
        explicit = (icp.get_param('report.url') or '').strip()
        if explicit:
            return explicit.rstrip('/')
        if icp.get_param(self.ICP_PDF_LOOPBACK, 'true').lower() in ('1', 'true', 'yes'):
            return self._report_pdf_internal_base_url()
        return None

    @api.model
    def _get_report_url(self, layout=None):
        base = self._get_report_base_for_pdf_assets()
        if base is not None:
            return base
        return super()._get_report_url(layout=layout)

    @api.model
    def _render_template(self, template, values=None):
        base = self._get_report_base_for_pdf_assets()
        if base is None:
            return super()._render_template(template, values)
        if values is None:
            values = {}
        values = dict(values)
        user = self.env['res.users'].browse(self.env.uid)
        view_obj = self.env['ir.ui.view'].with_context(inherit_branding=False)
        values.update(
            time=time,
            context_timestamp=lambda t: fields.Datetime.context_timestamp(self.with_context(tz=user.tz), t),
            user=user,
            res_company=self.env.company,
            web_base_url=base,
        )
        return view_obj._render_template(template, values).encode()
