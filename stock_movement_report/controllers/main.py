# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from odoo import http
from odoo.tools import html_escape
from odoo.http import content_disposition, request


class ReportController(http.Controller):

    @http.route('/get/favorite/list', type='jsonrpc', auth="user")
    def get_favorites_list(self, **kw):
        """ To fetch the favorite list """
        model_name = kw.get('model_name')
        if not model_name:
            return []

        ref_ids = request.env['ir.filters'].sudo().search_read(
            [
                ('model_id', 'ilike', model_name),
                ('user_ids', 'in', [request.env.user.id])
            ],
            ['id', 'name', 'filter_options', 'model_id']
        )
        return ref_ids

    @http.route('/save/fav_menu', type='jsonrpc', auth="user")
    def save_fav_menu(self, res_id, favorites):
        """ To save favourite menu """
        if res_id:
            request.env['ir.filters'].sudo().browse(int(res_id)).write({'name': favorites})
        return True

    @http.route('/check/fav_menu', type='jsonrpc', auth="user")
    def check_fav_menu(self, res_id, favorites):
        """ To check favourite menu """
        if not favorites:
            return False

        filters = request.env['ir.filters'].sudo().search([('name', '=', favorites)])
        if res_id:
            filters = filters.filtered(lambda f: f.id != int(res_id))
        return bool(filters)

    @http.route('/delete/fav_menu', type='jsonrpc', auth="user")
    def delete_fav_menu(self, res_id):
        """ To Delete favourite menu """
        if res_id:
            request.env['ir.filters'].sudo().browse(int(res_id)).unlink()

    @http.route('/web/save/favorites', type='jsonrpc', auth="user")
    def save_favorites(self, **kw):
        """ To Save favorites """
        model_name = kw.get('model_name')
        name = kw.get('favorites')
        if not model_name or not name:
            return False

        request.env['ir.filters'].sudo().create({
            'model_id': model_name,
            'name': name,
            'user_ids': [(4, request.env.user.id)],
            'filter_options': kw.get('filter_options') or '{}',
        })
        return True

    @http.route('/action_report_print', type='http', auth='user', methods=['POST'], csrf=False)
    def get_report_info(self, data, **kw):
        try:
            data_s = json.loads(data)
        except Exception:
            return request.make_response("Invalid data", headers=[('Content-Type', 'text/plain')])

        token = kw.get('csrf_token')
        model = data_s.get('model')
        options = data_s.get('options')
        report_format = data_s.get('report_format')

        if not (model and options and report_format):
            return request.make_response("Missing parameters", headers=[('Content-Type', 'text/plain')])

        report_obj = request.env[model].with_user(request.session.uid)
        return self.print_report(
            model=model,
            options=options,
            report_format=report_format,
            token=token,
            report_obj=report_obj,
            kw=kw
        )

    def print_report(self, model, options, report_format, token, report_obj=None, **kw):
        try:
            options = json.loads(options) if isinstance(options, str) else options
            report_name = report_obj.get_report_filename(options)

            if report_format == 'xlsx':
                response = request.make_response(
                    None,
                    headers=[
                        ('Content-Type', 'application/vnd.ms-excel'),
                        ('Content-Disposition', content_disposition(f"{report_name}.xlsx"))
                    ]
                )
                report_obj.get_xlsx(options, response)

            elif report_format == 'pdf':
                response = request.make_response(
                    report_obj.get_report_pdf(options),
                    headers=[
                        ('Content-Type', 'application/pdf'),
                        ('Content-Disposition', content_disposition(f"{report_name}.pdf"))
                    ]
                )
            else:
                return request.make_response("Unsupported format", headers=[('Content-Type', 'text/plain')])

            response.set_cookie('fileToken', token)
            return response

        except Exception as e:
            error = {
                'code': 200,
                'message': 'Odoo Server Error',
                'data': http.serialize_exception(e),
            }
            return request.make_response(html_escape(json.dumps(error)))
