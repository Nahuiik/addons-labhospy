# -*- coding: utf-8 -*-

import base64
from odoo import http
from odoo.http import request, content_disposition


class StockValuationBinary(http.Controller):

    @http.route('/web/binary/download_stock_valuation', type='http', auth="user")
    def download_document(self, model, field, id, filename=None, **kw):
        """
        Descarga de archivos almacenados como campos binarios.
        """
        Model = request.env[model].sudo()
        record = Model.browse(int(id))
        
        if not record.exists():
            return request.not_found()
        
        filecontent = base64.b64decode(record[field] or b'')
        
        if not filecontent:
            return request.not_found()
        
        if not filename:
            filename = f'{model.replace(".", "_")}_{id}'
        
        return request.make_response(
            filecontent,
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', content_disposition(filename))
            ]
        )
