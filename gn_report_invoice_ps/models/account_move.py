from dateutil import tz

from odoo import fields, models

class AccountMove(models.Model):
    _inherit = 'account.move'
    
    def print_invoice_point_sale(self):
        self.ensure_one()
        return self.env.ref('gn_report_invoice_ps.action_invoice_point_sale_report').report_action(self)
    
    def datatime_report_ps(self):
        self.ensure_one()
        from_zone = tz.gettz('UTC')
        to_zone = tz.gettz(self.env.context.get('tz')) or tz.gettz(self.env.user.tz) or tz.gettz('UTC')
        now_utc = fields.Datetime.now().replace(tzinfo=from_zone)
        now_local = now_utc.astimezone(to_zone)
        formatted_date = now_local.strftime("%d/%m/%Y")
        formatted_time = now_local.strftime("%H:%M:%S")
        return f'FECHA IMPRESION: {formatted_date}   {formatted_time}'
    
    def account_tax_report_ps(self):
        self.ensure_one()
        return self.env['account.tax'].search([('type_tax_use', '=', 'sale')])

    def change_size_page(self, items):
        self.ensure_one()
        paper_format = self.env.ref('gn_report_invoice_ps.invoice_point_sale_format').sudo()
        item_count = len(items)
        base_height = 297
        target_height = base_height
        if item_count > 10:
            target_height = 240 + (item_count * 12)
        if abs(paper_format.page_height - target_height) > 0.01:
            paper_format.write({'page_height': target_height})
        return False
