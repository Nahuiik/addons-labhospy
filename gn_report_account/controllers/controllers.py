# -*- coding: utf-8 -*-
# from odoo import http


# class GnReportAccount(http.Controller):
#     @http.route('/gn_report_account/gn_report_account/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/gn_report_account/gn_report_account/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('gn_report_account.listing', {
#             'root': '/gn_report_account/gn_report_account',
#             'objects': http.request.env['gn_report_account.gn_report_account'].search([]),
#         })

#     @http.route('/gn_report_account/gn_report_account/objects/<model("gn_report_account.gn_report_account"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('gn_report_account.object', {
#             'object': obj
#         })
