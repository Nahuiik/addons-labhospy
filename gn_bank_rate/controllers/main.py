from odoo import http, fields
from odoo.http import request


class BankRateController(http.Controller):
    @http.route('/gn_bank_rate/info', type='jsonrpc', auth='user')
    def get_bank_rate_info(self):
        env = request.env
        company = env.user.company_id
        currency = env.ref('base.USD', raise_if_not_found=False)
        rate_value = 0.0
        rate_date = False
        if currency:
            company_id = company.id if company else False
            rate = env['res.currency.rate'].sudo().search(
                [
                    ('currency_id', '=', currency.id),
                    '|',
                    ('company_id', '=', company_id),
                    ('company_id', '=', False),
                ],
                order='name desc',
                limit=1,
            )
            if rate:
                rate_value = rate.rate
                rate_date = rate.name
        server_time = fields.Datetime.now()
        user_time = fields.Datetime.context_timestamp(env.user, server_time) if server_time else None
        return {
            'rate': rate_value,
            'rate_date': rate_date,
            'time': user_time.isoformat() if user_time else False,
            'currency_symbol': currency.symbol if currency else '$',
        }
