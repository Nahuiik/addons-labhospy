from odoo import api, fields, models


class CustomerStatementReport(models.AbstractModel):
    _name = 'report.os_customer_vendor_statements.customer_statements_report'
    _description = 'Customer Statement Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        active_id = self.env.context.get('active_id') if not docids else docids[0]
        partner = self.env['res.partner'].browse(active_id)
        sorted_data = partner.customer_amount_ids.sorted(lambda x: x.name)
        data['d_dict'] = {'due_amt_total': round(sum([x.remaining_due_amount for x in sorted_data]), 2),
                          'credit_amt_total': round(sum([x.credit_amount for x in sorted_data]), 2),
                          'amt_signed_total': round(sum([x.amount_total_signed for x in sorted_data]), 2),
                          'balance_ids': sorted_data}
        return {'doc_ids': docids,
                'data': data,
                'partner': partner,
                'd_dict': data['d_dict']}


class CustomerOverdueStatementReport(models.AbstractModel):
    _name = 'report.os_customer_vendor_statements.customer_overdue_report'
    _description = 'Customer Overdue Statement Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        active_id = self.env.context.get('active_id') if not docids else docids[0]
        partner = self.env['res.partner'].browse(active_id)
        date_today = fields.Date.today()
        sorted_data = [move for move in [val for val in partner.customer_amount_ids if
                                         val.payment_state != 'paid' and val.invoice_date_due] if
                       move.invoice_date_due < date_today]
        data['d_dict'] = {'due_amt_total': round(sum([x.remaining_due_amount for x in sorted_data]), 2),
                          'credit_amt_total': round(sum([x.credit_amount for x in sorted_data]), 2),
                          'amt_signed_total': round(sum([x.amount_total_signed for x in sorted_data]), 2),
                          'balance_ids': sorted_data}
        return {'doc_ids': docids,
                'data': data,
                'partner': partner,
                'd_dict': data['d_dict']}


class VendorStatementReport(models.AbstractModel):
    _name = 'report.os_customer_vendor_statements.vendor_statements_report'
    _description = 'Vendor Statement Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        active_id = self.env.context.get('active_id') if not docids else docids[0]
        partner = self.env['res.partner'].browse(active_id)
        sorted_data = partner.vendor_amount_ids.sorted(lambda x: x.name)
        data['d_dict'] = {'due_amt_total': round(sum([x.remaining_due_amount for x in sorted_data]), 2),
                          'credit_amt_total': round(sum([x.credit_amount for x in sorted_data]), 2),
                          'amt_signed_total': round(sum([x.amount_total_signed for x in sorted_data]), 2),
                          'balance_ids': sorted_data}
        return {'doc_ids': docids,
                'data': data,
                'partner': partner,
                'd_dict': data['d_dict']}


class FilteredCustomerStatementReport(models.AbstractModel):
    _name = 'report.os_customer_vendor_statements.filtered_customer_report'
    _description = 'Filtered Customer Statement Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        active_id = self.env.context.get('active_id') if not docids else docids[0]
        partner = self.env['res.partner'].browse(active_id)
        sorted_data = partner.customer_filter_line_ids.sorted(lambda x: x.reference)
        data['d_dict'] = {'due_amt_total': round(sum([x.remaining_due_amount for x in sorted_data]), 2),
                          'credit_amt_total': round(sum([x.credit_amount for x in sorted_data]), 2),
                          'amt_signed_total': round(sum([x.amount_total_signed for x in sorted_data]), 2),
                          'balance_ids': sorted_data}
        return {'doc_ids': docids,
                'data': data,
                'partner': partner,
                'd_dict': data['d_dict']}


class FilteredVendorStatementReport(models.AbstractModel):
    _name = 'report.os_customer_vendor_statements.filtered_vendor_report'
    _description = 'Filtered Vendor Statement Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        active_id = self.env.context.get('active_id') if not docids else docids[0]
        partner = self.env['res.partner'].browse(active_id)
        sorted_data = partner.vendor_filter_line_ids.sorted(lambda x: x.reference)
        data['d_dict'] = {'due_amt_total': round(sum([x.remaining_due_amount for x in sorted_data]), 2),
                          'credit_amt_total': round(sum([x.credit_amount for x in sorted_data]), 2),
                          'amt_signed_total': round(sum([x.amount_total_signed for x in sorted_data]), 2),
                          'balance_ids': sorted_data}
        return {'doc_ids': docids,
                'data': data,
                'partner': partner,
                'd_dict': data['d_dict']}


class MonthlyStatementReport(models.AbstractModel):
    _name = 'report.os_customer_vendor_statements.monthly_customer_report'
    _description = 'Monthly Customer Statement Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        active_id = self.env.context.get('active_id') if not docids else docids[0]
        partner = self.env['res.partner'].browse(active_id)
        sorted_data = partner.monthly_customer_amount_ids.sorted(lambda x: x.name)
        data['d_dict'] = {'due_amt_total': round(sum([x.remaining_due_amount for x in sorted_data]), 2),
                          'credit_amt_total': round(sum([x.credit_amount for x in sorted_data]), 2),
                          'amt_signed_total': round(sum([x.amount_total_signed for x in sorted_data]), 2),
                          'balance_ids': sorted_data}
        return {'doc_ids': docids,
                'data': data,
                'partner': partner,
                'd_dict': data['d_dict']}


class WeeklyStatementReport(models.AbstractModel):
    _name = 'report.os_customer_vendor_statements.weekly_customer_report'
    _description = 'Weekly Customer Statement Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        active_id = self.env.context.get('active_id') if not docids else docids[0]
        partner = self.env['res.partner'].browse(active_id)
        sorted_data = partner.weekly_customer_amount_ids.sorted(lambda x: x.name)
        data['d_dict'] = {'due_amt_total': round(sum([x.remaining_due_amount for x in sorted_data]), 2),
                          'credit_amt_total': round(sum([x.credit_amount for x in sorted_data]), 2),
                          'amt_signed_total': round(sum([x.amount_total_signed for x in sorted_data]), 2),
                          'balance_ids': sorted_data}
        return {'doc_ids': docids,
                'data': data,
                'partner': partner,
                'd_dict': data['d_dict']}


class CustomStatementReport(models.AbstractModel):
    _name = 'report.os_customer_vendor_statements.custom_customer_report'
    _description = 'Custom Customer Statement Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        active_id = self.env.context.get('active_id') if not docids else docids[0]
        partner = self.env['res.partner'].browse(active_id)
        sorted_data = partner.custom_customer_amount_ids.sorted(lambda x: x.name)
        data['d_dict'] = {'due_amt_total': round(sum([x.remaining_due_amount for x in sorted_data]), 2),
                          'credit_amt_total': round(sum([x.credit_amount for x in sorted_data]), 2),
                          'amt_signed_total': round(sum([x.amount_total_signed for x in sorted_data]), 2),
                          'balance_ids': sorted_data}
        return {'doc_ids': docids,
                'data': data,
                'partner': partner,
                'd_dict': data['d_dict']}
