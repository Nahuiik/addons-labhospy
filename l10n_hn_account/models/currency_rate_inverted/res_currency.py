from odoo import api, fields, models
import requests
from bs4 import BeautifulSoup
from datetime import datetime



class ResCurrency(models.Model):
    _inherit = 'res.currency'

    rate_inverted = fields.Boolean(
        string='Inverted exchange rate',
        company_dependent=True,
    )

    @api.model
    def _get_conversion_rate(self, from_currency, to_currency, company, date):
        # Igual que res.currency: sin compañía, _get_rates() hace company.root_id y falla (RPC p.ej. al crear factura)
        company = company or self.env.company
        if not company:
            company = self.env['res.company'].sudo().search([], limit=1)
        date = date or fields.Date.context_today(self)
        rate = super()._get_conversion_rate(
            from_currency,
            to_currency,
            company,
            date
        )

        if not from_currency.rate_inverted and not to_currency.rate_inverted:
            return rate
        elif from_currency.rate_inverted and to_currency.rate_inverted:
            return 1 / rate

        currency_rates = (
            from_currency + to_currency
        )._get_rates(company, date)
        l_rate = currency_rates.get(to_currency.id)
        r_rate = currency_rates.get(from_currency.id)
        if not from_currency.rate_inverted and to_currency.rate_inverted:
            return 1 / (l_rate * r_rate)
        elif from_currency.rate_inverted and not to_currency.rate_inverted:
            return l_rate * r_rate

    @api.model
    def get_currency_rate_from_bank(self):
        # open with GET method
        rate = 0
        date = False
        try:
            url = 'https://www.banpais.hn/barradolar.php'
            r = requests.get(url, timeout=20)
            resp = requests.get(url)
            # http_respone 200 means OK status
            if resp.status_code == 200:
                # we need a parser,Python built-in HTML parser is enough .
                soup = BeautifulSoup(resp.text, 'html.parser')
                print('soup.findAll("b")[4].string ======', soup.findAll("b"))
                rate = soup.findAll("b")[1].string
                if rate:
                    rate = rate.strip()
                    rate = float(rate)
                    date = datetime.today().date()
                    print("Rate BanPais:", rate)
                   
                
        except requests.exceptions.Timeout as e:
            rate = 0
        except:
            pass

        if not rate:
            try:
                url = 'https://www.ficohsa.com/hn/honduras/tipo-cambio/'
                r = requests.get(url, timeout=20)

                resp = requests.get(url)
                # http_respone 200 means OK status
                if resp.status_code == 200:

                    # we need a parser,Python built-in HTML parser is enough .
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    rate = soup.findAll("p")[1].text
                    rate = rate.replace('Venta: Lps. ', '')
                    if rate:
                        rate = rate.strip()
                        rate = float(rate)

                        #get date
                        date_str = soup.findAll("h3")[0].text
                        if date_str:
                            date_str = date_str.split(',')[1].strip()
                            date = datetime.strptime(date_str, '%d/%m/%Y')

                        else:
                            date = datetime.today().date()
                

            except requests.exceptions.Timeout as e:
                rate = 0
            except:
                pass

        #update rate
        if rate and date:
            currency_id = self.env.ref('base.USD')
            try:
                per_day_rate_count = self.env['res.currency.rate'].search_count([('currency_id','=',currency_id.id), ('name', '=',date),])   
                if per_day_rate_count == 0:
                    # Si no existe una tasa para esa fecha, se una nueva
                    self.env['res.currency.rate'].create({
                        'currency_id': currency_id.id,
                        'name': date,
                        'rate': rate
                    })
                else:
                    # Si existe una tasa, se actualiza el valor de la tasa existente
                    currency_rate = self.env['res.currency.rate'].search([
                        ('currency_id', '=', currency_id.id),
                        ('name', '=', date)
                    ], limit=1)
                    currency_rate.write({'rate': rate})  
            except:
                pass

        


