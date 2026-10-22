# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request, route
from odoo.addons.web.controllers import report
import json
from urllib.parse import quote


class ReportController(report.ReportController):

    @http.route(['/report/download'], type='http', auth="user")
    def report_download(self, data, context=None, token=None):
        res = super().report_download(data, context, token)
        requestcontent = json.loads(data)
        url, type_ = requestcontent[0], requestcontent[1]

        if type_ not in ['qweb-pdf', 'qweb-text']:
            return res
        pattern = '/report/pdf/' if type_ == 'qweb-pdf' else '/report/text/'
        reportname = url.split(pattern)[1].split('?')[0]
    
        docids = None
        if '/' in reportname:
            reportname, docids = reportname.split('/')
        report = request.env['ir.actions.report']._get_report_from_name(reportname)

        res.headers.add("Report-Name", reportname)
        res.headers.add("Report-Title", quote(report.name))
        res.headers.add("Report-Print-Options", report.print_report_options) 

        if not docids:
            return res

        ids = [int(x) for x in docids.split(",") if x.isdigit()]
        rec = request.env[report.model].browse(ids) 
        report_names = ",".join([r.display_name for r in rec])

        res.headers.add("Report-Docnames", quote(report_names))
        return res