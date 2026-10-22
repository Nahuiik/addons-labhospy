from odoo import api, fields, models, _
from odoo.tools import float_compare
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def _get_default_branch(self):
        User = self.env['res.users']
        return User.browse(self.env.uid).branch_id.id or False

    branch_id = fields.Many2one('res.branch', 'Branch', default=_get_default_branch)

    @api.onchange('branch_id')
    def onchange_branch_id(self):
        if self.branch_id:
            if self.branch_id.term_conditions:
                self.note = self.branch_id.term_conditions
            # if self.branch_id.gst_no:
            #     self.df_gst_number = self.branch_id.gst_no
            wh = self.env['stock.warehouse'].search([('branch_id', '=',self.branch_id.id)])
            if wh:
                self.warehouse_id = wh[0]
            else:
                self.warehouse_id = False

    def _prepare_invoice(self):
        res = super(SaleOrder, self)._prepare_invoice()
        res.update({
            'branch_id': self.branch_id.id,
            'journal_id': self.env.user.journal_default_id.id or self.branch_id.journal_id.id or False,
        })
        return res

    def action_confirm(self):
        result = super(SaleOrder, self).action_confirm()
        purchase_orders = self._get_purchase_orders()
        if purchase_orders:
            purchase_orders.write({'branch_id': self.branch_id.id})
        return result
    

    # def _create_invoices(self, grouped=False, final=False, date=None):
    #     """ Sobreescribir esta funcion para agregar el diario y la sucursal correcta a la factura """
    #     result = super(SaleOrder, self)._create_invoices(grouped, final, date)
    #     for invoice in result:
    #         invoice.write({'branch_id': self.branch_id.id})
    #     return result

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'company_id' in vals:
                self = self.with_company(vals['company_id'])

            if vals.get('name', _("New")) == _("New"):
                seq_date = None
                if 'date_order' in vals:
                    # Convierte date_order a datetime naive
                    date_order_dt = fields.Datetime.to_datetime(vals['date_order'])
                    seq_date = fields.Datetime.context_timestamp(self, date_order_dt)
                    seq_date = seq_date.replace(tzinfo=None)

                branch = self.env['res.branch'].browse(vals.get('branch_id'))
                sequence = branch.sale_sequence_id if branch and branch.sale_sequence_id else None

                if sequence:
                    vals['name'] = sequence.with_context(ir_sequence_date=seq_date).next_by_id()
                else:
                    vals['name'] = self.env['ir.sequence'].next_by_code(
                        'sale.order', sequence_date=seq_date
                    ) or _("New")

        return super().create(vals_list)
