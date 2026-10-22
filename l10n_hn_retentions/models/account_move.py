from odoo import _, api, fields, models, tools
from datetime import datetime

class AccountMove(models.Model):
    _inherit = 'account.move'

    retention_sequence = fields.Char(string='Retention Sequence')
    ret_amount_1 = fields.Float(string='Retention 1%',compute='_compute_amounts_retentions')
    ret_amount_12_5 = fields.Float(string='Retention 12.5%',compute='_compute_amounts_retentions')
    ret_amount_15 = fields.Float(string='Retention 15%',compute='_compute_amounts_retentions')
    is_payment_account = fields.Boolean(string='', related='partner_id.is_payment_account')
    state_date_payments_account = fields.Selection(string='', selection=[('validate', 'Date Validate'), ('overdue', 'Date Overdue'),('not_established','Date Not Established')], compute="_compute_date_account")
    partner_name = fields.Char(string='Name of partner', related='partner_id.name')


    @api.depends(
        'invoice_line_ids',
        'invoice_line_ids.retention_types_ids',
        'invoice_line_ids.quantity',
        'invoice_line_ids.price_unit',
    )
    def _compute_amounts_retentions(self):
        for rec in self:
            ret_amount_12_5=0.00
            if rec.amount_untaxed>=0.00:
                rec.ret_amount_1 = rec.amount_untaxed*(1/100)
                rec.ret_amount_15 = rec.amount_untaxed*(15/100)
            for line in rec.invoice_line_ids:
                if line.retention_types_ids:
                    ret_amount_12_5 += (line.quantity*line.price_unit)*(12.5/100)
            rec.ret_amount_12_5 = ret_amount_12_5

    @api.onchange('invoice_line_ids')
    def _onchange_invoice_line_ids_retentions(self):
        """Actualiza ret_amount_12_5 en tiempo real al editar líneas sin guardar.

        @api.onchange solo acepta nombres de campos del propio modelo, no rutas
        con punto. El cambio dentro de las líneas dispara igualmente este
        onchange al monitorear el One2many directamente.
        """
        if self.move_type not in ('in_invoice', 'in_refund', 'in_receipt'):
            return
        ret_amount_12_5 = 0.0
        for line in self.invoice_line_ids:
            if line.retention_types_ids:
                ret_amount_12_5 += (line.quantity * line.price_unit) * (12.5 / 100)
        self.ret_amount_12_5 = ret_amount_12_5

    def _compute_amount(self):
        return super(AccountMove, self)._compute_amount()
    def _compute_date_account(self):
        for rec in self:
            if rec.is_payment_account:
                now = datetime.now().date()
                if rec.partner_id.date_payments_account:
                    if rec.partner_id.date_payments_account>=now:
                        rec.state_date_payments_account='validate'
                    else:
                        rec.state_date_payments_account='overdue'
                else:
                    rec.state_date_payments_account='not_established'
            else:
                rec.state_date_payments_account=''

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    retention_types_ids = fields.Many2many('gn_retentions.retentions.type', string="Ret %")
    retention_amount_12_5 = fields.Monetary(
        string="Retención 12.5%",
        compute='_compute_retention_amount_12_5',
        store=True,
        currency_field='currency_id',
    )

    @api.onchange('product_id')
    def _onchange_product_id_retention_types(self):
        """Asigna retention_types_ids al seleccionar producto, sin necesidad de guardar."""
        if self.move_id and self.move_id.move_type in ('in_invoice', 'in_refund', 'in_receipt'):
            if self.display_type in ('line_section', 'line_subsection', 'line_note'):
                self.retention_types_ids = False
                return
            if self.product_id and self.product_id.type == 'service':
                tag = self.env.ref('l10n_hn_retentions.retention_12_5_data', raise_if_not_found=False)
                if tag:
                    self.retention_types_ids = tag
            else:
                self.retention_types_ids = False

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._l10n_hn_retentions_sync_retention_types()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ('product_id', 'move_id', 'display_type')):
            self._l10n_hn_retentions_sync_retention_types()
        return res

    def _l10n_hn_retentions_sync_retention_types(self):
        """Asigna retention_types_ids en líneas de servicio de facturas de proveedor.

        _compute_amount del move no incluye product_id en sus depends, por eso
        al agregar una línea con servicio el tag no se asignaba. Usamos create/write
        para sincronizar en el momento correcto.
        """
        tag = self.env.ref('l10n_hn_retentions.retention_12_5_data', raise_if_not_found=False)
        if not tag:
            return
        for line in self:
            if not line.move_id or line.move_id.move_type not in ('in_invoice', 'in_refund', 'in_receipt'):
                continue
            if line.display_type in ('line_section', 'line_subsection', 'line_note'):
                line.retention_types_ids = False
                continue
            if line.product_id and line.product_id.type == 'service':
                line.retention_types_ids = tag
            else:
                line.retention_types_ids = False

    @api.depends('quantity', 'price_unit', 'retention_types_ids', 'product_id', 'product_id.type')
    def _compute_retention_amount_12_5(self):
        for line in self:
            if line.retention_types_ids and line.product_id and line.product_id.type == 'service':
                line.retention_amount_12_5 = (line.quantity * line.price_unit) * (12.5 / 100)
            else:
                line.retention_amount_12_5 = 0.0
