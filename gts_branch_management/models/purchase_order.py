from odoo import api, fields, models, _
from odoo.exceptions import UserError

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.model
    def _get_default_branch(self):
        User = self.env['res.users']
        return User.browse(self.env.uid).branch_id.id or False

    @api.onchange('branch_id')
    def _onchange_branch_id(self):
        if self.branch_id:
            if self.branch_id.term_conditions_purchase:
                self.note = self.branch_id.term_conditions_purchase
            picking_type = self.env['stock.picking.type'].search([('code', '=', 'incoming'),
                                     ('warehouse_id.branch_id', '=',
                                      self.branch_id.id)])
            if picking_type:
                self.picking_type_id = picking_type[0]
            else:
                raise UserError(
                    _("No Warehouse has the branch same as the one selected "
                      "in the Purchase Order")
                )

    branch_id = fields.Many2one('res.branch', 'Branch', required=False, default=_get_default_branch)

    @api.model
    def _prepare_picking(self):
        vals = super()._prepare_picking()
        vals['branch_id'] = self.branch_id.id
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        orders = self.browse()
        partner_vals_list = []
        for vals in vals_list:
            company_id = vals.get('company_id', self.default_get(['company_id'])['company_id'])
            self_comp = self.with_company(company_id)

            if vals.get('name', 'New') == 'New':
                seq_date = None
                if 'date_order' in vals:
                    seq_date = fields.Datetime.to_datetime(vals['date_order'])
                    if seq_date.tzinfo:
                        seq_date = seq_date.replace(tzinfo=None)

                # buscar secuencia en branch_id
                sequence = None
                if vals.get('branch_id'):
                    branch = self.env['res.branch'].browse(vals['branch_id'])
                    sequence = branch.purchase_sequence_id

                if sequence:
                    vals['name'] = sequence.with_context(ir_sequence_date=seq_date).next_by_id() or '/'
                else:
                    # fallback: usar secuencia global de purchase.order
                    vals['name'] = self_comp.env['ir.sequence'].next_by_code(
                        'purchase.order', sequence_date=seq_date
                    ) or '/'

            vals, partner_vals = self._write_partner_values(vals)
            partner_vals_list.append(partner_vals)
            orders |= super(PurchaseOrder, self_comp).create(vals)

        for order, partner_vals in zip(orders, partner_vals_list):
            if partner_vals:
                order.sudo().write(partner_vals)

        return orders

    def _write_partner_values(self, vals):
        """Split partner-related updates from incoming vals before create."""
        partner_values = {}
        if 'receipt_reminder_email' in vals:
            partner_values['receipt_reminder_email'] = vals.pop('receipt_reminder_email')
        if 'reminder_date_before_receipt' in vals:
            partner_values['reminder_date_before_receipt'] = vals.pop('reminder_date_before_receipt')
        return vals, partner_values
