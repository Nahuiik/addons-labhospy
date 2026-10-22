from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError,ValidationError

class AccountPaymentFix(models.Model):
    """Fix: Use permanent model for write-off lines"""
    _inherit = 'account.payment'
    
    # Override to use permanent model instead of transient
    write_off_lines = fields.One2many('payment.writeoff', 'payment_id', string="Writeoff Lines", copy=False)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Convert transient write-off lines to permanent ones"""
        # Store write-off data separately (can't add to vals)
        pending_write_offs = []
        
        for vals in vals_list:
            # Extract write-off info if present
            if 'write_off_line_vals' in vals and vals.get('post_diff_in') == 'multi':
                write_off_line_vals = vals.get('write_off_line_vals', [])
                # Don't pass write_off_lines in vals (avoid transient model issue)
                vals.pop('write_off_lines', None)
                pending_write_offs.append(write_off_line_vals)
            else:
                pending_write_offs.append(None)
        
        # Create the payment records
        payments = super(AccountPaymentFix, self).create(vals_list)
        
        # Now create permanent write-off records
        for payment, write_off_data in zip(payments, pending_write_offs):
            if write_off_data:
                write_off_lines = []
                for line_vals in write_off_data:
                    # IMPORTANT: Only create writeoff for lines with account_id
                    # The first line in write_off_line_vals may not have account_id (it's just a total marker)
                    account_id = line_vals.get('account_id')
                    if account_id and account_id != False:  # Explicit check
                        # Try to extract amount_per from description or calculate it
                        description = line_vals.get('name', '')
                        amount = abs(line_vals.get('amount_currency', 0))
                        
                        # Extract percentage from description if available
                        amount_per = 0
                        if 'amount_per' in line_vals:
                            amount_per = line_vals['amount_per']
                        elif '1%' in description or '1 %' in description:
                            amount_per = 1.0
                        elif '12.5%' in description or '12.5 %' in description:
                            amount_per = 12.5
                        elif '15%' in description or '15 %' in description:
                            amount_per = 15.0
                        
                        write_off_lines.append((0, 0, {
                            'payment_id': payment.id,
                            'account_id': account_id,
                            'description': description or 'Write-off',
                            'amount_per': amount_per,
                            'amount': amount,
                        }))
                
                if write_off_lines:
                    payment.with_context(skip_payment_write_lock=True).write({
                        'write_off_lines': write_off_lines,
                    })
        
        return payments

class AccountPaymentRegisterFix(models.TransientModel):
    """Clean up write-off lines to avoid duplicates and lines without account_id"""
    _inherit = 'account.payment.register'
    
    def _create_payment_vals_from_wizard(self, batch_result):
        """Clean up write_off_line_vals after parent modules process them"""
        # Call parent (which may include gts_multiple_invoice_payment_currency)
        payment_vals = super(AccountPaymentRegisterFix, self)._create_payment_vals_from_wizard(batch_result)
        
        # LIMPIAR write_off_line_vals: eliminar duplicados y líneas sin account_id
        if 'write_off_line_vals' in payment_vals:
            write_off_line_vals = payment_vals.get('write_off_line_vals', [])
            
            # Filtrar líneas sin account_id
            valid_lines = [
                line_vals for line_vals in write_off_line_vals
                if line_vals.get('account_id') not in (False, None)
            ]
            
            # Deduplicar por (account_id, amount_currency)
            seen = set()
            deduplicated_lines = []
            for line_vals in valid_lines:
                key = (line_vals.get('account_id'), line_vals.get('amount_currency'))
                if key not in seen:
                    seen.add(key)
                    deduplicated_lines.append(line_vals)
            
            # Reemplazar con las líneas limpias
            payment_vals['write_off_line_vals'] = deduplicated_lines

        return payment_vals

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    apply_retentions = fields.Boolean(string='Apply Retention')
    retention_1 = fields.Boolean(string="Retention 1%")
    retention_12_5 = fields.Boolean(string="Retention 12.5%")
    retention_15 = fields.Boolean(string="Retencion 15%")
    amount_ret_1 = fields.Float(string='')
    amount_ret_12_5 = fields.Float(string='')
    amount_ret_15 = fields.Float(string='')
    is_payment_account = fields.Boolean(string='',related='partner_id.is_payment_account')
    account_ret_1  = fields.Many2one(comodel_name='account.account', string='Account Retention 1%', compute='_compute_accounts_retention')
    account_ret_12_5  = fields.Many2one(comodel_name='account.account', string='Account Retention 12.5%', compute='_compute_accounts_retention')
    account_ret_15 = fields.Many2one(comodel_name='account.account', string='Account Retention 15%', compute='_compute_accounts_retention')
    show_retention_option = fields.Boolean(string='Show Retention Option', compute='_compute_show_retention_visibility')
    show_retention_1 = fields.Boolean(string='Show Retention 1%', compute='_compute_show_retention_visibility')
    show_retention_12_5 = fields.Boolean(string='Show Retention 12.5%', compute='_compute_show_retention_visibility')
    show_retention_15 = fields.Boolean(string='Show Retention 15%', compute='_compute_show_retention_visibility')

    @staticmethod
    def _get_config_param(params, suffix, default='False'):
        new_key = f'l10n_hn_retentions.{suffix}'
        legacy_key = f'l10n_hn_gn_retentions.{suffix}'
        value = params.get_param(new_key)
        if value in (None, False, ''):
            value = params.get_param(legacy_key, default)
        return default if value in (None, False, '') else value

    @api.depends('payment_type', 'company_id')
    def _compute_show_retention_visibility(self):
        params = self.env['ir.config_parameter'].sudo()
        for wizard in self:
            supplier_flow = wizard.payment_type == 'outbound'
            customer_flow = wizard.payment_type == 'inbound'

            if supplier_flow:
                option_enabled = tools.str2bool(
                    self._get_config_param(params, 'apply_retentions')
                )
                show_1 = tools.str2bool(
                    self._get_config_param(params, 'apply_1')
                )
                show_12 = tools.str2bool(
                    self._get_config_param(params, 'apply_12_5')
                )
                show_15 = tools.str2bool(
                    self._get_config_param(params, 'apply_15')
                )
            elif customer_flow:
                option_enabled = tools.str2bool(
                    self._get_config_param(params, 'apply_customer_retentions')
                )
                show_1 = tools.str2bool(
                    self._get_config_param(params, 'apply_customer_1')
                )
                show_12 = tools.str2bool(
                    self._get_config_param(params, 'apply_customer_12_5')
                )
                show_15 = tools.str2bool(
                    self._get_config_param(params, 'apply_customer_15')
                )
            else:
                option_enabled = False
                show_1 = False
                show_12 = False
                show_15 = False

            wizard.show_retention_option = option_enabled
            wizard.show_retention_1 = option_enabled and show_1
            wizard.show_retention_12_5 = option_enabled and show_12
            wizard.show_retention_15 = option_enabled and show_15

            if not wizard.show_retention_option:
                wizard.apply_retentions = False
                wizard.retention_1 = False
                wizard.retention_12_5 = False
                wizard.retention_15 = False
            else:
                if not wizard.show_retention_1:
                    wizard.retention_1 = False
                    wizard.amount_ret_1 = 0.0
                if not wizard.show_retention_12_5:
                    wizard.retention_12_5 = False
                    wizard.amount_ret_12_5 = 0.0
                if not wizard.show_retention_15:
                    wizard.retention_15 = False
                    wizard.amount_ret_15 = 0.0
    @api.depends('account_ret_1','account_ret_12_5','account_ret_15')
    def _compute_accounts_retention(self):
        ICPSudo = self.env['ir.config_parameter'].sudo()
        for rec in self:
            if rec.payment_type == 'outbound':
                account_ret_1 = self._get_config_param(ICPSudo, 'account_ret_1', '')
                account_ret_12_5 = self._get_config_param(ICPSudo, 'account_ret_12_5', '')
                account_ret_15 = self._get_config_param(ICPSudo, 'account_ret_15', '')
                rec.account_ret_1 = int(account_ret_1) if account_ret_1 else False
                rec.account_ret_12_5 = int(account_ret_12_5) if account_ret_12_5 else False
                rec.account_ret_15 = int(account_ret_15) if account_ret_15 else False

            if rec.payment_type == 'inbound':
                account_ret_1 = self._get_config_param(ICPSudo, 'account_customer_ret_1', '')
                account_ret_12_5 = self._get_config_param(ICPSudo, 'account_customer_ret_12_5', '')
                account_ret_15 = self._get_config_param(ICPSudo, 'account_customer_ret_15', '')
                rec.account_ret_1 = int(account_ret_1) if account_ret_1 else False
                rec.account_ret_12_5 = int(account_ret_12_5) if account_ret_12_5 else False
                rec.account_ret_15 = int(account_ret_15) if account_ret_15 else False

    @api.onchange('retention_1','retention_12_5','amount_ret_1', 'amount_ret_12_5','retention_15')
    def _onchange_retention(self):
        for rec in self:
            if not rec.show_retention_option:
                rec.apply_retentions = False
                rec.retention_1 = False
                rec.retention_12_5 = False
                rec.retention_15 = False
                rec.amount = rec.source_amount
                rec.write_off_lines = [(5, 0, 0)]
                rec.payment_difference_handling = 'open'
                continue
            if not rec.show_retention_1:
                rec.retention_1 = False
                rec.amount_ret_1 = 0.0
            if not rec.show_retention_12_5:
                rec.retention_12_5 = False
                rec.amount_ret_12_5 = 0.0
            if not rec.show_retention_15:
                rec.retention_15 = False
                rec.amount_ret_15 = 0.0
            # Reconstruir SIEMPRE las líneas de write-off según las retenciones
            # marcadas (una o varias). Antes solo se llenaban para combinaciones
            # que incluían el 1% (1%+12.5%, 1%+15%, las tres); por eso una
            # retención ÚNICA —o la combinación 12.5%+15% sin 1%— no agregaba
            # ninguna línea. Ahora cada retención marcada genera su línea con el
            # mismo camino 'multi', de modo que el comportamiento es consistente.
            rec.write_off_lines = [(5, 0, 0)]
            rec.writeoff_account_id = False
            rec.writeoff_label = False

            lines = []
            total_ret = 0.0
            if rec.retention_1 and rec.account_ret_1:
                lines.append((0, 0, {
                    'account_id': rec.account_ret_1.id,
                    'description': 'Retención 1%',
                    'amount_per': 1.0,
                    'amount': rec.amount_ret_1,
                }))
                total_ret += rec.amount_ret_1 or 0.0
            if rec.retention_12_5 and rec.account_ret_12_5:
                lines.append((0, 0, {
                    'account_id': rec.account_ret_12_5.id,
                    'description': 'Retención 12.5%',
                    'amount_per': 12.5,
                    'amount': rec.amount_ret_12_5,
                }))
                total_ret += rec.amount_ret_12_5 or 0.0
            if rec.retention_15 and rec.account_ret_15:
                lines.append((0, 0, {
                    'account_id': rec.account_ret_15.id,
                    'description': 'Retención 15%',
                    'amount_per': 15.0,
                    'amount': rec.amount_ret_15,
                }))
                total_ret += rec.amount_ret_15 or 0.0

            if rec.retention_1 or rec.retention_12_5 or rec.retention_15:
                # IMPORTANTE: el importe debe ser el BRUTO (residual completo),
                # NO el neto (source - retención). El asiento del pago se arma con
                # CxP(débito) = amount y Banco = amount - retención, y luego
                # gts concilia (amount_neto_factura + retención) = residual contra
                # esa CxP. Si aquí netáramos el amount, la CxP quedaría corta y se
                # sobre-conciliaría (residual negativo) además de descontar la
                # retención DOS veces del banco. Con el bruto: CxP=residual,
                # Banco=residual-retención, retención y conciliación cuadran exacto.
                rec.amount = rec.source_amount
                rec.payment_difference_handling = 'reconcile'
                rec.post_diff_in = 'multi'
                rec.write_off_lines = lines
            else:
                rec.amount = rec.source_amount
                rec.payment_difference_handling = 'open'
                rec.post_diff_in = 'single'


                

    @api.onchange('source_amount', 'retention_1', 'retention_12_5','retention_15')
    def compute_retention(self):
        for rec in self:
            active_ids = self.env.context.get('active_ids')
            invoices = self.env['account.move.line'].browse(active_ids).mapped('move_id')
            ret_12 = 0
            ret_12_aux = 0
            for inv in invoices:
                if rec.amount_ret_1 == 0:
                    rec.amount_ret_1 = (inv.amount_untaxed * 0.01)
                if rec.amount_ret_15 == 0:
                    rec.amount_ret_15 = (inv.amount_untaxed * 0.15)

                rec.amount_ret_12_5 = 0
                for line in inv.invoice_line_ids:
                    # product_id.type es un campo relacionado que viene de product.template.type
                    if line.product_id and line.product_id.type == 'service' and line.retention_types_ids:
                        rec.amount_ret_12_5 += (line.quantity*line.price_unit)*(12.5/100)

                # for line in inv.invoice_line_ids:
                #     # if line.product_id.type == 'service':
                #     # if line.product_id.type == 'service' and line.retention_types_ids:
                #         ret_12 = (inv.amount_untaxed * 0.125)
                #     else :
                #         ret_12_aux = 0.00
                # if rec.amount_ret_12_5 == 0:
                #     if ret_12 >= ret_12_aux:
                #         rec.amount_ret_12_5 = ret_12
                #     else:
                #         rec.amount_ret_12_5 = ret_12_aux

    def action_partner_name(self):
        return True

    def _l10n_hn_cap_invoice_amounts_to_payment(self, invoice_amounts):
        """Ajusta los importes por factura al monto real del pago (pagos parciales)."""
        self.ensure_one()
        if not invoice_amounts:
            return invoice_amounts
        wizard_amount = abs(self.amount)
        currency = self.currency_id
        total_alloc = sum(invoice_amounts.values())
        if currency.compare_amounts(total_alloc, wizard_amount) <= 0:
            return invoice_amounts
        move_ids = list(invoice_amounts.keys())
        allocated = 0.0
        for i, move_id in enumerate(move_ids):
            if i == len(move_ids) - 1:
                invoice_amounts[move_id] = currency.round(wizard_amount - allocated)
            else:
                share = invoice_amounts[move_id] / total_alloc if total_alloc else 0.0
                part = currency.round(wizard_amount * share)
                invoice_amounts[move_id] = part
                allocated += part
        return invoice_amounts

    def _create_payment_vals_from_wizard(self, batch_result):
        res = super(AccountPaymentRegister, self)._create_payment_vals_from_wizard(batch_result)
        invoice_amounts = {}
        invoice_totals = {}
        invoice_residuals = {}
        lines = batch_result.get('lines') or self.line_ids
        for aml in lines:
            move = aml.move_id
            if not move:
                continue
            amount_currency = aml.amount_residual_currency if aml.currency_id else aml.amount_residual
            amount_to_pay = abs(amount_currency)
            invoice_amounts[move.id] = invoice_amounts.get(move.id, 0.0) + amount_to_pay
            invoice_totals.setdefault(move.id, abs(move.amount_total))
            invoice_residuals.setdefault(move.id, abs(move.amount_residual))

        if invoice_amounts:
            invoice_amounts = self._l10n_hn_cap_invoice_amounts_to_payment(invoice_amounts)
            res_invoice_lines = []
            for move_id, amount in invoice_amounts.items():
                line_vals = {
                    'invoice_id': move_id,
                    'amount': amount,
                    'amount_total': invoice_totals.get(move_id, amount),
                    'residual': invoice_residuals.get(move_id, amount),
                }
                res_invoice_lines.append((0, 0, line_vals))
            res['invoice_lines'] = res_invoice_lines

        res_config = self.company_id.is_exclude_receipt
        journal_id = self.env['account.journal'].search([('is_retention','=',True)], limit=1)
        seq = ''
        if journal_id.is_retention:
            seq = journal_id.retention_seq.next_by_code('supplier.retention')
        move_ids=account_move=''
        if res:
            move_ids = res.get('invoice_lines')[0][2].get('invoice_id')

        if move_ids:
            account_move = self.env['account.move'].search([('id','=',move_ids)])
        permise_retentions = False

        if account_move.move_type == 'in_invoice':
            if res_config:
                if self.partner_id:
                    if not self.partner_id.is_payment_account:
                        permise_retentions=True
                    else:
                        if not self.partner_id.date_payments_account:
                            raise ValidationError(_('El proveedor %s tiene pago a cuenta y fecha no válida.', self.partner_id.name))
                        if not self.payment_date:
                            raise UserError(_("Fecha del pago no válida."))
                        if not account_move.invoice_date:
                            raise UserError(_("Fecha de la factura no válida."))
                        if self.partner_id.date_payments_account< self.payment_date or self.partner_id.date_payments_account< account_move.invoice_date:
                            permise_retentions=True
            else:
                permise_retentions=True

            if account_move.move_type == 'in_invoice':
                if (self.retention_1 or self.retention_12_5) and (permise_retentions==False):
                    raise ValidationError(_('El proveedor %s tiene pagos a cuenta, no se aplicará retención.', self.partner_id.name))
        
        if account_move.move_type == 'out_invoice':
            permise_retentions = True

        if (self.retention_1 or self.retention_12_5 or self.retention_15) and permise_retentions == True and self.show_retention_option:

            active_ids = self.env.context.get('active_ids', [])
            invoices = self.env['account.move.line'].browse(active_ids).mapped('move_id')
            
            if account_move.move_type == 'in_invoice':
                invoices.write({'retention_sequence':seq })
                # Actualiza los valores del encabezado de account.payment
                sequence = self.env['ir.sequence']
                sequence_id = sequence.search([('code','=','retention.seq.supplier')])
                code = sequence.next_by_code('retention.seq.supplier') or ''

            # Retenciones se generan vía _prepare_move_withholding_lines, no write_off_line_vals
            res.update({
                'apply_retentions': True,
                'apply_1': self.retention_1,
                'apply_12_5': self.retention_12_5,
                'apply_15': self.retention_15,
                'retention_sequence_id': code if account_move.move_type == 'in_invoice' else False,
                'retention_sequence_ids': sequence_id[0].id if account_move.move_type == 'in_invoice' else False,
            })

            # Distribuir retenciones en TODAS las invoice_lines: amount = residual - retenciones por factura
            total_ret = (self.amount_ret_1 or 0) + (self.amount_ret_12_5 or 0) + (self.amount_ret_15 or 0)
            total_residual = sum(invoice_residuals.values()) or 1.0
            for cmd, _x, line_vals in res.get('invoice_lines', []):
                if cmd != 0:
                    continue
                move_id = line_vals.get('invoice_id')
                if not move_id:
                    continue
                inv = self.env['account.move'].browse(move_id)
                residual = invoice_residuals.get(move_id, 0)
                if total_residual and total_ret and residual:
                    share = residual / total_residual
                    ret_1 = (self.amount_ret_1 or 0) * share
                    ret_12_5 = (self.amount_ret_12_5 or 0) * share
                    ret_15 = (self.amount_ret_15 or 0) * share
                else:
                    ret_1 = ret_12_5 = ret_15 = 0.0
                amount_net = residual - ret_1 - ret_12_5 - ret_15
                line_vals.update({
                    'amount': max(0, amount_net),
                    'amount_retention_1': ret_1,
                    'amount_retention_12_5': ret_12_5,
                    'amount_retention_15': ret_15,
                })
        # print(po)
        return res
    def action_create_payments(self):
        res = super().action_create_payments()
        return res