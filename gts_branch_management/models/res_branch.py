from odoo import api, fields, models

class BranchBranch(models.Model):
    _name = 'res.branch'
    _description = "Branch"

    branch_code = fields.Char('Branch Code/Ref.')
    name = fields.Char('Name', required=True)
    address = fields.Text('Branch Address')
    telephone_no = fields.Char('Telephone No.')
    gst_no = fields.Char('GSTIN')
    state_id = fields.Many2one('res.country.state', 'State')
    company_id = fields.Many2one('res.company', 'Company', required=True)
    term_conditions = fields.Text('Terms and Conditions (Quotation/Order)')
    term_conditions1 = fields.Text('Terms and Conditions (Invoice)')
    term_conditions_proforma = fields.Text('Terms and Conditions (Proforma)')
    term_conditions_purchase = fields.Text('Terms and Conditions (Purchase)')
    
    journal_id = fields.Many2one('account.journal', string="Journal", domain=[('type', '=', 'sale')])
    purchase_journal_id = fields.Many2one('account.journal', string="Purchase Journal",
                                          domain=[('type', '=', 'purchase')])
    principal = fields.Boolean(string="Principal")

    pdf_watermark_branch = fields.Binary(
        'Invoice Template PDF',
        help='Upload a watermark PDF to be used as the background of each page printed.\n\
                    Watermark uploaded here will override the one uploaded at company \
                    level in the general settings.')
    pdf_watermark_fname_branch = fields.Char('Watermark filename (invoice PDF)')

    pdf_watermark_branch_order = fields.Binary(
        'Quote Template PDF',
        help='Upload a watermark PDF to be used as the background of each page printed.\n\
                    Watermark uploaded here will override the one uploaded at company \
                    level in the general settings.')
    pdf_watermark_fname_branch_order = fields.Char('Watermark filename (quote PDF)')

    sale_sequence_id = fields.Many2one('ir.sequence', string="Secuencia de Venta", copy=False)
    purchase_sequence_id = fields.Many2one('ir.sequence', string="Secuencia de Compra", copy=False)
