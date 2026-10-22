from odoo import models, api, fields
import requests
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging
import json
import base64

_logger = logging.getLogger(__name__)


class Currency(models.Model):
    _inherit = 'res.currency'

    @api.model
    def get_currency_bch_rate_from_bank(self):
        _logger.info('Cron Job - Get Currency Rate from Bank')
        rate = 0
        date = False
        today_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - relativedelta(days=10)).strftime('%Y-%m-%d')

        attachment = None
        status_label = 'Error'
        raw_json = None

        try:
            _logger.info('Requesting Currency Rate from Bank')
            url = (
                "https://bchapi-am.azure-api.net/api/v1/indicadores/620/cifras"
                f"?formato=Json&fechaInicio={start_date}&ordenamiento=desc"
            )
            hdr = {
                'Cache-Control': 'no-cache',
                'clave': '96d3219533804541a7b27099b75c4653',            
            }

            response = requests.get(url, headers=hdr, timeout=20)

            # Siempre intentamos adjuntar el JSON de respuesta si existe
            try:
                raw_json = response.json()
            except Exception:
                raw_json = {'error': 'No fue posible decodificar JSON', 'status_code': response.status_code}

            if raw_json:
                attachment = self._create_json_attachment(raw_json)

            if response.status_code == 200 and isinstance(raw_json, list) and raw_json:
                _logger.info('Response success from Bank')
                rate = raw_json[0].get('Valor', 0)
                date = raw_json[0].get('Fecha')

                # Iterar sobre todas las compañías
                companies = self.env['res.company'].search([])
                currency = self.env.ref('base.USD')

                for company in companies:
                    exist_rate = self.env['res.currency.rate'].search([
                        ('name', '=', today_date),
                        ('currency_id', '=', currency.id),
                        ('company_id', '=', company.id)
                    ])
                    if exist_rate:
                        exist_rate.unlink()

                    rate_created = self.env['res.currency.rate'].create({
                        'name': today_date,
                        'rate': rate,
                        'currency_id': currency.id,
                        'company_id': company.id,
                    })
                    _logger.info('Rate updated for company %s: %s', company.name, rate_created)
                status_label = 'Éxito'
            else:
                _logger.error('HTTP %s from BCH API', response.status_code)
                status_label = f'Error HTTP {response.status_code}'
        except Exception as exc:
            _logger.exception('Exception while getting BCH rate: %s', exc)
            status_label = 'Error'

        # Enviar correo con adjunto (si lo hay)
        self.send_email_currency_rate(status_label, rate, date, attachment_id=attachment.id if attachment else None)

    def _create_json_attachment(self, data_json):
        """Crea y devuelve un ir.attachment con el JSON de respuesta."""
        try:
            company = self.env.user.company_id
            pretty = json.dumps(data_json, ensure_ascii=False, indent=2)
            payload = pretty.encode('utf-8')
            b64 = base64.b64encode(payload)

            filename = f"bch_rate_response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            att = self.env['ir.attachment'].sudo().create({
                'name': filename,
                'datas': b64,
                'res_model': 'res.company',        # lo asociamos a la compañía para tener referente
                'res_id': company.id,
                'mimetype': 'application/json',
            })
            return att
        except Exception as exc:
            _logger.exception('No se pudo crear el adjunto JSON: %s', exc)
            return None

    def send_email_currency_rate(self, status, rate, date, attachment_id=None):
        company = self.env.user.company_id
        company_email = company.email
        # Si quieres respetar HN sin hacks, puedes usar la zona del usuario:
        # tz = self.env.user.tz or 'America/Tegucigalpa'
        # date_run = fields.Datetime.context_timestamp(self, datetime.now()).strftime('%d/%m/%Y %H:%M:%S')
        date_run = (datetime.now() - relativedelta(hours=6)).strftime('%d/%m/%Y %H:%M:%S')

        logo_html = ''
        if company.logo:
            logo_b64 = company.logo.decode('utf-8')
            logo_html = (
                f'<img src="data:image/png;base64,{logo_b64}" alt="Logo" '
                'style="max-height:60px;margin:0 auto 20px;display:block;" />'
            )

        body = f"""
        <div style="max-width:600px;margin:0 auto;padding:20px;border:1px solid #ddd;border-radius:8px;font-family:'Lato',sans-serif;background:#fff;">
            {logo_html}
            <h2 style="color:#333;text-align:center;">Actualización de Tasa de Cambio</h2>

            <p style="font-size:16px;color:#444;">
                A continuación se presenta el informe automático con la información más reciente sobre la
                tasa de cambio obtenida desde el <strong>BCH</strong>:
            </p>

            <ul style="font-size:16px;color:#444;list-style:none;padding-left:0;">
                <li><strong>Estado:</strong> {status}</li>
                <li><strong>Tasa de Cambio:</strong> {rate}</li>
                <li><strong>Fecha de la Tasa:</strong> {date}</li>
                <li><strong>Fecha de Ejecución:</strong> {date_run}</li>
            </ul>

            <p style="text-align:center;margin:30px 0;">
                <a href="{company.website or '#'}"
                   style="background:#875A7B;color:#fff;padding:12px 25px;border-radius:6px;text-decoration:none;font-weight:bold;">
                   Ir al sistema
                </a>
            </p>

            <hr style="margin:20px 0;border:0;border-top:1px solid #eee;"/>

            <table width="100%" style="text-align:center;font-size:12px;color:#aaa;">
                <tr>
                    <td>
                        {company.name or ''}<br/>
                        {company.phone or ''} | {company.email or ''} | {company.website or ''}
                    </td>
                </tr>
            </table>

            <div style="text-align:center;margin-top:10px;font-size:12px;color:#bbb;">
                Con la tecnología de <strong style="color:#875A7B;">Odoo</strong>
            </div>
        </div>
        """

        mail_vals = {
            'subject': '📈 Informe de Tasa de Cambio BCH',
            'body_html': body,
            'email_to': company_email,
            'email_from': company_email or 'noreply@odoo.com',
            'auto_delete': True,
        }

        if attachment_id:
            mail_vals['attachment_ids'] = [(6, 0, [attachment_id])]

        if company_email:
            mail = self.env['mail.mail'].sudo().create(mail_vals)
            _logger.info('Sending BCH rate email to %s', company_email)
            mail.sudo().send()
            _logger.info('BCH rate email sent')
        else:
            _logger.warning('No company email defined; cannot send BCH rate email.')
