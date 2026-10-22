# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import content_disposition, request

_logger = logging.getLogger(__name__)

_MAX_PRODUCTS = 20000


class StockAtDateXlsxController(http.Controller):

    @http.route(
        '/gn_labhospy/stock_at_date_xlsx',
        type='http',
        auth='user',
        methods=['POST'],
        csrf=True,
    )
    def download(self, ids=None, context=None, **kwargs):
        if not request.env.user.has_group('stock.group_stock_user'):
            return request.make_response(
                'Forbidden',
                headers=[('Content-Type', 'text/plain')],
                status=403,
            )
        try:
            product_ids = json.loads(ids or '[]')
            raw_context = json.loads(context or '{}')
        except (TypeError, ValueError):
            return request.make_response(
                'Invalid data',
                headers=[('Content-Type', 'text/plain')],
                status=400,
            )
        if not isinstance(product_ids, list) or not isinstance(raw_context, dict):
            return request.make_response(
                'Invalid data',
                headers=[('Content-Type', 'text/plain')],
                status=400,
            )
        if len(product_ids) > _MAX_PRODUCTS:
            return request.make_response(
                'Too many products',
                headers=[('Content-Type', 'text/plain')],
                status=400,
            )
        try:
            content, filename = request.env['product.product'].gn_labhospy_stock_at_date_xlsx(
                product_ids,
                raw_context,
            )
        except Exception:
            _logger.exception('Excel de inventario a la fecha')
            return request.make_response(
                'Error',
                headers=[('Content-Type', 'text/plain')],
                status=500,
            )
        return request.make_response(
            content,
            headers=[
                (
                    'Content-Type',
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                ),
                ('Content-Disposition', content_disposition(filename)),
            ],
        )
