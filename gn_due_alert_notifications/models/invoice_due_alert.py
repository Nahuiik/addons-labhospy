# -*- coding: utf-8 -*-
from odoo import api, models, _


class InvoiceDueAlert(models.AbstractModel):
    _inherit = 'gn.invoice.due.alert'

    def _push_popup(self, user, title, message, sticky=True, warning=True):
        company = self.env.company
        if company.gn_due_notif_enabled and company.gn_due_notif_realtime_enabled:
            return
        return super()._push_popup(
            user, title, message, sticky=sticky, warning=warning)

    @api.model
    def _run_notifications(self, manual=False, popup=True, email=True):
        Engine = self.env['gn.due.alert.engine']
        total_users = 0
        for company in self.env['res.company'].search([]):
            if not manual and not company.due_alert_enabled:
                continue
            send_email = email
            if email and not manual:
                send_email = Engine._should_send_daily_summary(company)
            svc = self.with_company(company)
            info = svc._collect(company)
            bills = svc._open_bills(company)
            c = info['raw_counts']
            relevant = c['today'] + c['soon'] + (
                c['overdue'] if company.due_alert_include_overdue else 0)
            if not relevant:
                continue
            users = svc._alert_users()
            title = _('Facturas de proveedor por pagar')
            message = svc._popup_message(
                info, company, bills=bills,
                today=info['today'], currency=info['currency'])
            for user in users:
                if popup and user.partner_id:
                    svc._push_popup(
                        user, title, message,
                        sticky=company.due_alert_popup_sticky)
                if send_email and user.email:
                    svc._send_email(user, info, company, bills=bills)
                total_users += 1
            if send_email and not manual:
                Engine._mark_daily_summary_sent(company)
        return total_users


class CustomerDueAlert(models.AbstractModel):
    _inherit = 'gn.customer.due.alert'

    def _push_popup(self, user, title, message, sticky=True, warning=True):
        company = self.env.company
        if company.gn_due_notif_enabled and company.gn_due_notif_realtime_enabled:
            return
        return super()._push_popup(
            user, title, message, sticky=sticky, warning=warning)

    @api.model
    def _run_notifications(self, manual=False, popup=True, email=True):
        Engine = self.env['gn.due.alert.engine']
        total_users = 0
        for company in self.env['res.company'].search([]):
            if not manual and not company.customer_due_alert_enabled:
                continue
            send_email = email
            if email and not manual:
                send_email = Engine._should_send_daily_summary(company)
            svc = self.with_company(company)
            info = svc._collect(company)
            invoices = svc._open_invoices(company)
            c = info['raw_counts']
            relevant = c['today'] + c['soon'] + (
                c['overdue'] if company.customer_due_alert_include_overdue else 0)
            if not relevant:
                continue
            users = svc._alert_users()
            title = _('Facturas de cliente por cobrar')
            message = svc._popup_message(
                info, company, invoices=invoices,
                today=info['today'], currency=info['currency'])
            for user in users:
                if popup and user.partner_id:
                    svc._push_popup(
                        user, title, message,
                        sticky=company.customer_due_alert_popup_sticky)
                if send_email and user.email:
                    svc._send_email(user, info, company, invoices=invoices)
                total_users += 1
            if send_email and not manual:
                Engine._mark_daily_summary_sent(company)
        return total_users
