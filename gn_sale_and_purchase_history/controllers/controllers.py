# -*- coding: utf-8 -*-
# from odoo import http


# class GnSaleAndPurchaseHistory(http.Controller):
#     @http.route('/gn_sale_and_purchase_history/gn_sale_and_purchase_history/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/gn_sale_and_purchase_history/gn_sale_and_purchase_history/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('gn_sale_and_purchase_history.listing', {
#             'root': '/gn_sale_and_purchase_history/gn_sale_and_purchase_history',
#             'objects': http.request.env['gn_sale_and_purchase_history.gn_sale_and_purchase_history'].search([]),
#         })

#     @http.route('/gn_sale_and_purchase_history/gn_sale_and_purchase_history/objects/<model("gn_sale_and_purchase_history.gn_sale_and_purchase_history"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('gn_sale_and_purchase_history.object', {
#             'object': obj
#         })
