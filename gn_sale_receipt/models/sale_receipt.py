# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools, Command
from odoo.exceptions import UserError, ValidationError


class SaleReceipt(models.Model):
    _name = "sale.receipt"
    _description = "Sale Receipt"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, name desc"

    name = fields.Char(string="Número", required=True, default="Draft", copy=False, tracking=True, readonly=True)
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("posted", "Publicado"),
            ("cancelled", "Cancelado"),
        ],
        string="Estado",
        default="draft",
        tracking=True,
    )
    company_id = fields.Many2one("res.company", string="Compañía", required=True, default=lambda self: self.env.company)
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        tracking=True,
        required=True,
        domain="[('customer_rank', '>', 0)]",
    )
    def _default_receipt_journal(self):
        # Primero intentar obtener el diario desde los parámetros de configuración
        journal_id = int(self.env['ir.config_parameter'].sudo().get_param('sale_receipt.default_journal_id', 0))
        if journal_id:
            journal = self.env['account.journal'].browse(journal_id)
            if journal.exists() and journal.for_sale_receipt and journal.type == 'general':
                return journal
        
        # Si no hay uno configurado, buscar automáticamente un diario marcado como "Para recibos de venta"
        journal = self.env['account.journal'].search([
            ('type', '=', 'general'),
            ('for_sale_receipt', '=', True),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        
        if journal:
            return journal
        
        return self.env['account.journal']

    def _default_payment_journal(self):
        journal_id = int(self.env['ir.config_parameter'].sudo().get_param('sale_receipt.default_payment_method_journal_id', 0))
        if journal_id:
            return self.env['account.journal'].browse(journal_id)
        return self.env['account.journal']

    journal_receipt_id = fields.Many2one(
        "account.journal",
        string="Diario",
        domain="[('type', '=', 'general'), ('for_sale_receipt', '=', True)]",
        tracking=True,
        default=_default_receipt_journal,
        required=True,
    )
    
    @api.onchange("journal_receipt_id", "date")
    def _onchange_journal_receipt_id(self):
        """Previsualizar la secuencia cuando se selecciona o cambia el diario"""
        # NO consumir la secuencia aquí - solo previsualizar
        # La secuencia se consumirá solo en create() para evitar duplicados
        # Si el recibo ya existe (tiene ID), no hacer nada
        if self.id:
            return
        # Solo mostrar "Draft" en la vista - la secuencia se generará al guardar
        if not self.name or self.name == "Draft":
            if self.journal_receipt_id and self.journal_receipt_id.sequence_id:
                # Mostrar "Draft" hasta que se guarde - la secuencia se generará en create()
                pass
    date = fields.Date(string="Fecha contable", default=fields.Date.context_today, tracking=True)
    payment_ref = fields.Text(string="Notas")
    user_cashier_id = fields.Many2one("res.users", string="Cajero", default=lambda self: self.env.user, tracking=True)
    payment_way = fields.Selection(
        [
            ("direct", "Pagar directamente"),
            ("transfer", "Transferencia"),
            ("other", "Otro"),
        ],
        string="Pago",
        default="direct",
    )
    payment_method_journal_id = fields.Many2one(
        "account.journal",
        string="Método de pago",
        domain="[('type', 'in', ('cash','bank'))]",
        default=_default_payment_journal,
    )

    line_ids = fields.One2many("sale.receipt.line", "receipt_id", string="Líneas", copy=True)
    invoice_line_ids = fields.One2many("sale.receipt.invoice.line", "receipt_id", string="Asignaciones", copy=True)

    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    amount_untaxed = fields.Monetary(string="Base", compute="_compute_amounts", store=True)
    amount_tax = fields.Monetary(string="Impuestos", compute="_compute_amounts", store=True)
    amount_total = fields.Monetary(string="Total", compute="_compute_amounts", store=True)
    amount_to_text = fields.Char(string="Cantidad en letras", compute="_compute_amount_to_text")

    move_id = fields.Many2one("account.move", string="Asiento contable", copy=False, readonly=True)

    invoice_ids = fields.Many2many(
        "account.move",
        "sale_receipt_account_move_rel",
        "receipt_id",
        "invoice_id",
        string="Facturas",
        domain="[('move_type','in',('out_invoice','out_refund'))]",
        readonly=True,
    )

    @api.depends("line_ids.price_subtotal", "line_ids.price_tax")
    def _compute_amounts(self):
        for receipt in self:
            untaxed = sum(receipt.line_ids.mapped("price_subtotal"))
            tax = sum(receipt.line_ids.mapped("price_tax"))
            receipt.amount_untaxed = untaxed
            receipt.amount_tax = tax
            receipt.amount_total = untaxed + tax

    @api.depends("amount_total", "currency_id")
    def _compute_amount_to_text(self):
        for receipt in self:
            amount = receipt.amount_total or 0.0
            currency = receipt.currency_id or receipt.company_id.currency_id
            if not currency:
                receipt.amount_to_text = ""
                continue
            try:
                receipt.amount_to_text = currency.amount_to_text(amount, lang="es_HN")
            except TypeError:
                receipt.amount_to_text = currency.amount_to_text(amount)

    @api.constrains("invoice_line_ids", "amount_total")
    def _check_assignment_total(self):
        for receipt in self:
            if receipt.state == "draft" and receipt.invoice_line_ids:
                assigned = sum(receipt.invoice_line_ids.mapped("assigned_amount"))
                if tools.float_compare(assigned, receipt.amount_total, precision_rounding=receipt.currency_id.rounding) != 0:
                    raise ValidationError(_("La suma asignada a facturas debe coincidir con el total del recibo."))

    def copy(self, default=None):
        """Sobrescribir el método copy para resetear campos al duplicar"""
        default = default or {}
        default.update({
            'name': 'Draft',  # Resetear el nombre para que se genere nueva secuencia
            'state': 'draft',  # Resetear el estado
            'move_id': False,  # No copiar el asiento contable
        })
        return super().copy(default)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Solo generar secuencia si el nombre es "Draft" o no existe
            # Esto evita regenerar la secuencia si ya se generó
            if not vals.get("name") or vals.get("name") == "Draft":
                journal_id = vals.get("journal_receipt_id")
                if not journal_id:
                    # Si no hay diario al crear, usar secuencia por defecto
                    # Pero el diario es obligatorio, así que esto no debería pasar normalmente
                    seq = self.env["ir.sequence"].next_by_code("sale.receipt")
                    vals["name"] = seq or "Draft"
                else:
                    # El diario es obligatorio y debe tener sequence_id (obligatorio)
                    journal = self.env["account.journal"].browse(journal_id)
                    if not journal.sequence_id:
                        raise ValidationError(
                            _("El diario %s no tiene una secuencia configurada. Por favor configure la secuencia en el diario.")
                            % journal.name
                        )
                    
                    # CONSUMIR la secuencia SOLO AQUÍ - una sola vez al crear
                    sequence_date = vals.get("date") or fields.Date.context_today(self)
                    seq = journal.sequence_id.next_by_id(sequence_date=sequence_date)
                    if seq:
                        vals["name"] = seq
                    else:
                        vals["name"] = "Draft"
            # Si ya tiene un nombre válido (no es "Draft"), no hacer nada
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Acciones (sujetas a implementación completa en fases posteriores)
    # ------------------------------------------------------------------
    def action_get_invoices(self):
        self.ensure_one()
        return {
            "name": _("Obtener facturas"),
            "type": "ir.actions.act_window",
            "res_model": "sale.receipt.invoice.assign.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_receipt_id": self.id,
            },
        }

    def action_post(self):
        for receipt in self:
            if receipt.state != 'draft':
                raise UserError(_("Solo se pueden publicar recibos en estado borrador."))
            
            if not receipt.journal_receipt_id:
                raise UserError(_("Debe seleccionar un diario para el recibo."))
            
            if not receipt.payment_method_journal_id:
                raise UserError(_("Debe seleccionar un método de pago."))
            
            if not receipt.payment_method_journal_id.default_account_id:
                raise UserError(
                    _("El método de pago %s no tiene una cuenta configurada.")
                    % receipt.payment_method_journal_id.name
                )
            
            if not receipt.line_ids:
                raise UserError(_("El recibo debe tener al menos una línea."))
            
            # Validar que todas las líneas tengan cuenta
            lines_without_account = receipt.line_ids.filtered(lambda l: not l.account_id)
            if lines_without_account:
                raise UserError(
                    _("Las siguientes líneas no tienen cuenta configurada: %s")
                    % ', '.join(lines_without_account.mapped('name'))
                )
            
            # Verificar que el recibo tenga su secuencia generada antes de crear el asiento
            # NO generar aquí - la secuencia ya debe estar generada en create()
            if not receipt.name or receipt.name == "Draft":
                raise ValidationError(
                    _("El recibo debe tener una secuencia generada antes de validar. "
                      "Por favor guarde el recibo primero para generar la secuencia.")
                )
            
            # El asiento contable debe heredar el número del recibo (no usar secuencia del diario)
            # Usar el nombre del recibo directamente como nombre del asiento
            move_name = receipt.name
            
            company_currency = receipt.company_id.currency_id
            line_ids = []
            
            # Línea DEBITO: Cuenta del método de pago (por el total)
            # La cuenta de banco NO debe llevar el contacto (partner_id)
            payment_account = receipt.payment_method_journal_id.default_account_id
            payment_account_type = payment_account.account_type if payment_account else False
            
            # Para la línea de débito (banco), usar la descripción de las líneas del recibo si hay
            # Si hay múltiples líneas, concatenar las descripciones
            debit_name = receipt.partner_id.name or receipt.name
            if receipt.line_ids:
                line_descriptions = [line.name for line in receipt.line_ids if line.name]
                if line_descriptions:
                    # Usar la primera descripción o concatenar si hay varias
                    debit_name = ' | '.join(line_descriptions[:3])  # Limitar a 3 descripciones
                    if len(line_descriptions) > 3:
                        debit_name += '...'
            
            debit_line_vals = {
                'name': debit_name,
                'account_id': payment_account.id,
                'debit': receipt.amount_total,
                'credit': 0.0,
                # NO incluir partner_id en la cuenta de banco
                'date': receipt.date,
            }
            
            # Solo agregar date_maturity si la cuenta es por cobrar o por pagar
            # Para cuentas de activo corriente no es necesario
            if payment_account_type in ('asset_receivable', 'liability_payable'):
                debit_line_vals['date_maturity'] = receipt.date
            
            if receipt.currency_id != company_currency:
                debit_line_vals['currency_id'] = receipt.currency_id.id
                debit_line_vals['amount_currency'] = receipt.amount_total
            
            line_ids.append(Command.create(debit_line_vals))
            
            # Líneas CREDITO: Cuentas de las líneas del recibo
            for line in receipt.line_ids:
                if not line.account_id:
                    continue
                
                # Obtener la cuenta completa para verificar su tipo
                account = line.account_id
                # Asegurarse de leer el account_type correctamente
                account_type = account.account_type if account else False
                
                # Usar la descripción de la línea del recibo en la etiqueta del asiento
                line_name = line.name or receipt.partner_id.name or receipt.name
                credit_line_vals = {
                    'name': line_name,
                    'account_id': account.id,
                    'debit': 0.0,
                    'credit': line.price_subtotal,
                    'partner_id': receipt.partner_id.id,
                    'date': receipt.date,
                }
                
                # Si la cuenta es por cobrar o por pagar, agregar fecha de vencimiento
                # IMPORTANTE: Establecer siempre date_maturity para cuentas por cobrar/pagar
                if account_type in ('asset_receivable', 'liability_payable'):
                    credit_line_vals['date_maturity'] = receipt.date
                
                # Agregar cuenta analítica si existe
                if line.analytic_account_id:
                    credit_line_vals['analytic_distribution'] = {
                        str(line.analytic_account_id.id): 100.0
                    }
                
                if receipt.currency_id != company_currency:
                    credit_line_vals['currency_id'] = receipt.currency_id.id
                    credit_line_vals['amount_currency'] = -line.price_subtotal
                
                line_ids.append(Command.create(credit_line_vals))
            
            # Si hay impuestos, crear líneas adicionales para los impuestos
            # Agrupar impuestos por cuenta
            tax_accounts = {}
            for line in receipt.line_ids:
                if line.price_tax > 0 and line.tax_ids:
                    # Agrupar por cada impuesto y su cuenta
                    for tax in line.tax_ids:
                        # Obtener la cuenta del impuesto
                        tax_account = False
                        if tax.invoice_repartition_line_ids:
                            repartition_line = tax.invoice_repartition_line_ids.filtered(
                                lambda r: r.repartition_type == 'tax'
                            )[:1]
                            if repartition_line:
                                tax_account = repartition_line.account_id
                        
                        if not tax_account:
                            tax_account = tax.account_id
                        
                        if tax_account:
                            key = tax_account.id
                            if key not in tax_accounts:
                                tax_accounts[key] = {
                                    'account': tax_account,
                                    'amount': 0.0
                                }
                            # Distribuir el monto del impuesto proporcionalmente
                            # Si hay múltiples impuestos, dividir el total
                            if len(line.tax_ids) > 1:
                                # Calcular el monto del impuesto específico
                                taxes_result = line.tax_ids.compute_all(
                                    line.price_unit,
                                    currency=receipt.currency_id,
                                    quantity=line.quantity
                                )
                                for tax_data in taxes_result.get('taxes', []):
                                    if tax_data['id'] == tax.id:
                                        tax_accounts[key]['amount'] += tax_data['amount']
                            else:
                                tax_accounts[key]['amount'] += line.price_tax
            
            # Crear líneas de impuestos
            for tax_account_data in tax_accounts.values():
                if tax_account_data['amount'] > 0:
                    tax_account = tax_account_data['account']
                    tax_line_vals = {
                        'name': receipt.partner_id.name or _("Impuestos"),
                        'account_id': tax_account.id,
                        'debit': 0.0,
                        'credit': tax_account_data['amount'],
                        'partner_id': receipt.partner_id.id,
                        'date': receipt.date,
                    }
                    
                    # Si la cuenta es por cobrar o por pagar, agregar fecha de vencimiento
                    tax_account_type = tax_account.account_type if tax_account else False
                    if tax_account_type in ('asset_receivable', 'liability_payable'):
                        tax_line_vals['date_maturity'] = receipt.date
                    
                    if receipt.currency_id != company_currency:
                        tax_line_vals['currency_id'] = receipt.currency_id.id
                        tax_line_vals['amount_currency'] = -tax_account_data['amount']
                    
                    line_ids.append(Command.create(tax_line_vals))
            
            # Crear el asiento contable
            # Usar tipo 'entry' para asientos contables simples (no facturas)
            # Usar contexto para evitar problemas con campos de solo lectura y evitar que journal_sequence consuma secuencia
            move_vals = {
                'journal_id': receipt.journal_receipt_id.id,
                'date': receipt.date,
                'ref': receipt.name,  # Usar la secuencia del recibo como referencia
                'move_type': 'entry',  # Tipo de asiento contable simple
                'partner_id': receipt.partner_id.id,
                'company_id': receipt.company_id.id,
                'name': move_name,  # El asiento hereda el número del recibo (NO consumir secuencia aquí)
                'sequence_generated': True,  # IMPORTANTE: Evitar que journal_sequence consuma otra secuencia
                'line_ids': line_ids,
            }
            
            # Crear el asiento contable en modo draft
            move = self.env['account.move'].with_context(
                check_move_validity=False,
                skip_invoice_sync=True,
            ).create(move_vals)
            
            # Asegurar que la línea de débito (cuenta de banco) NO tenga partner_id
            # Buscar la línea de débito de la cuenta del método de pago y eliminar partner_id
            payment_account = receipt.payment_method_journal_id.default_account_id
            if payment_account:
                # Primero intentar con ORM
                debit_line = move.line_ids.filtered(
                    lambda l: l.account_id.id == payment_account.id and l.debit > 0
                )
                if debit_line:
                    debit_line.with_context(check_move_validity=False).write({'partner_id': False})
                    # También usar SQL directo para asegurar que se elimine completamente
                    line_ids_tuple = tuple(debit_line.ids) if len(debit_line.ids) > 1 else (debit_line.ids[0],)
                    self.env.cr.execute("""
                        UPDATE account_move_line 
                        SET partner_id = NULL 
                        WHERE id IN %s AND account_id = %s AND debit > 0
                    """, (line_ids_tuple, payment_account.id))
                    move.invalidate_recordset(['line_ids'])
                    self.env.flush_all()
            
            # Asegurar que todas las líneas con cuentas por cobrar/pagar tengan date_maturity
            # Esto es CRÍTICO: debe establecerse antes de action_post() para evitar el error
            # Verificar usando SQL directo para obtener el account_type correcto
            move.invalidate_recordset(['line_ids'])
            self.env.flush_all()
            
            # Obtener todas las líneas que necesitan date_maturity usando SQL
            self.env.cr.execute("""
                SELECT aml.id, aa.account_type
                FROM account_move_line aml
                JOIN account_account aa ON aml.account_id = aa.id
                WHERE aml.move_id = %s
                AND aa.account_type IN ('asset_receivable', 'liability_payable')
                AND (aml.date_maturity IS NULL OR aml.date_maturity != %s)
            """, (move.id, receipt.date))
            
            lines_to_update = [row[0] for row in self.env.cr.fetchall()]
            
            if lines_to_update:
                # Establecer date_maturity usando SQL directo para asegurar que se guarde
                line_ids_tuple = tuple(lines_to_update)
                self.env.cr.execute("""
                    UPDATE account_move_line 
                    SET date_maturity = %s
                    WHERE id IN %s
                """, (receipt.date, line_ids_tuple))
                
                # Invalidar cache y forzar flush
                move.invalidate_recordset(['line_ids'])
                self.env.flush_all()
                
                # Verificar una vez más después del flush usando SQL
                self.env.cr.execute("""
                    SELECT aml.id
                    FROM account_move_line aml
                    JOIN account_account aa ON aml.account_id = aa.id
                    WHERE aml.move_id = %s
                    AND aa.account_type IN ('asset_receivable', 'liability_payable')
                    AND aml.date_maturity IS NULL
                """, (move.id,))
                
                remaining_ids_list = [row[0] for row in self.env.cr.fetchall()]
                if remaining_ids_list:
                    # Último intento forzando el update
                    remaining_ids_tuple = tuple(remaining_ids_list)
                    self.env.cr.execute("""
                        UPDATE account_move_line 
                        SET date_maturity = %s
                        WHERE id IN %s
                    """, (receipt.date, remaining_ids_tuple))
                    self.env.cr.commit()  # Forzar commit
                    move.invalidate_recordset(['line_ids'])
                    self.env.flush_all()
            
            # Asegurar que el nombre y sequence_generated estén establecidos
            if move.name != move_name or not move.sequence_generated:
                move.with_context(skip_compute_name=True, check_move_validity=False).write({
                    'name': move_name,
                    'sequence_generated': True,
                })
            
            # Validar el asiento - ahora todas las líneas con cuenta por cobrar/pagar tienen date_maturity
            move.action_post()
            
            # Vincular el asiento al recibo
            receipt.write({
                'move_id': move.id,
                'state': 'posted'
            })

    def action_cancel(self):
        for receipt in self:
            if receipt.state != 'posted':
                raise UserError(_("Solo se pueden cancelar recibos en estado publicado."))
            
            # Cancelar el asiento contable si existe
            if receipt.move_id:
                move = receipt.move_id
                if move.state == 'posted':
                    # CRÍTICO: Desconciliar TODAS las líneas ANTES de intentar poner en borrador
                    # El módulo gn_cancel_entrys valida payment_state == 'paid' en button_draft()
                    # y lanza el error antes de que podamos hacer algo, así que debemos desconciliar primero
                    
                    # Desconciliar todas las líneas reconciliadas
                    reconciled_lines = move.line_ids.filtered(lambda l: l.reconciled)
                    if reconciled_lines:
                        reconciled_lines.remove_move_reconcile()
                    
                    # También verificar si hay líneas parcialmente reconciliadas
                    partially_reconciled = move.line_ids.filtered(
                        lambda l: l.matched_debit_ids or l.matched_credit_ids
                    )
                    if partially_reconciled:
                        partially_reconciled.remove_move_reconcile()
                    
                    # Forzar el refresh del payment_state después de desconciliar
                    move.invalidate_recordset(['payment_state'])
                    move._compute_payment_state()
                    
                    # Asegurarse de que el payment_state no sea 'paid' antes de llamar a button_draft()
                    # Si aún es 'paid', establecerlo manualmente
                    if move.payment_state == 'paid':
                        move._compute_payment_state()
                        # Si aún es 'paid', intentar forzar el cambio
                        move.invalidate_recordset(['payment_state'])
                    
                    # Ahora intentar volver a borrador
                    move.button_draft()
                    # Luego cancelar
                    move.button_cancel()
                elif move.state == 'draft':
                    move.button_cancel()
            
            # Cambiar el estado del recibo a cancelado
            receipt.state = 'cancelled'

    def action_reset_to_draft(self):
        for receipt in self:
            if receipt.state != 'cancelled':
                raise UserError(_("Solo se pueden restablecer recibos en estado cancelado."))
            
            # Si hay asiento contable, restablecerlo también
            if receipt.move_id:
                if receipt.move_id.state == 'cancel':
                    # Restablecer el asiento contable a borrador
                    receipt.move_id.button_draft()
                elif receipt.move_id.state == 'posted':
                    raise UserError(
                        _("No se puede restablecer un recibo con asiento contable publicado. "
                          "Debe cancelar el asiento primero.")
                    )
            
            # Cambiar el estado del recibo a borrador
            receipt.state = "draft"

    def action_view_move(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No hay asiento contable asociado."))
        return {
            "name": _("Asiento contable"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.move_id.id,
            "target": "current",
        }
    
    def action_print_receipt(self):
        """Imprimir el recibo de venta usando el formato de recibo de pagos"""
        self.ensure_one()
        if not self.state == 'posted':
            raise UserError(_("El recibo debe estar publicado para poder imprimirlo."))
        
        # Intentar usar el reporte por XML ID, si no existe, buscarlo
        try:
            report = self.env.ref('gn_sale_receipt.sale_receipt_report_action', raise_if_not_found=False)
            if report:
                return report.report_action(self)
        except:
            pass
        
        # Si no se encontró por XML ID, buscar por modelo
        report = self.env['ir.actions.report'].search([
            ('model', '=', 'sale.receipt'),
            ('report_type', '=', 'qweb-pdf'),
        ], limit=1)
        
        if report:
            return report.report_action(self)
        else:
            raise UserError(_("No se encontró un reporte disponible para imprimir el recibo. Por favor actualice el módulo."))
