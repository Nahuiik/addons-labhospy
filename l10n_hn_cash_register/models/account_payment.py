from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    number_check = fields.Char(string='Número de cheque')
    date_check = fields.Date(string='Fecha de cheque')
    is_purchase = fields.Boolean(
        string='Purchase Bank Journal',
        help='Indica si el pago proviene de un diario marcado para compras con control de cheques.'
    )

    # Constraint to cheq_name, only allow numbers
    @api.constrains('number_check')
    def _check_number_check(self):
        for record in self:
            if record.number_check:
                if not record.number_check.isdigit():
                    raise ValidationError(_("El número de cheque solo puede contener números"))
