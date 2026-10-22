from odoo import models, fields, api


class BankDocuments(models.Model):
    _name = 'bank.documents'
    _description = 'bank documents'

    
    name = fields.Char(string="Name", required=True)
    file_name = fields.Char(string="File Name")
    file = fields.Binary(string="Document")
    bank_debit_id = fields.Many2one('debit.credit', string="Debit")
