from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    is_purchase = fields.Boolean(
        string='Purchase Bank Journal',
        related='journal_id.is_purchase',
        readonly=True,
    )
    number_check = fields.Char(string='Número de cheque')
    date_check = fields.Date(string='Fecha de cheque')
    
    def _create_payment_vals_from_wizard(self, batch_result):
        res = super()._create_payment_vals_from_wizard(batch_result)
        if self.is_purchase:
            res.update({
                'is_purchase': self.is_purchase,
                'number_check': self.number_check,
                'date_check': self.date_check,
            })
        return res

    # Constraint to cheq_name, only allow numbers
    @api.constrains('number_check')
    def _check_number_check(self):
        for record in self:
            if record.number_check:
                if not record.number_check.isdigit():
                    raise ValidationError(_("El número de cheque solo puede contener números"))
