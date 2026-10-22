from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.base.models.ir_sequence import _predict_nextval
from datetime import datetime
import re

class AccountMove(models.Model):
    _inherit = "account.move"

    cai_shot = fields.Char("Código CAI", related="partner_id.cai_shot", readonly=True)
    cai_invoice = fields.Char("CAI", readonly=True)
    cai_expires_shot = fields.Date("Expiration Date", readonly=True)
    min_number_shot = fields.Char(readonly=True, string="Minimum Number")
    max_number_shot = fields.Char(readonly=True, string="Maximum Number")
    # amount_total_text = fields.Char("Amount in Word", compute='get_totalt', default='Cero')
    predict_next_number = fields.Char(compute='_get_predict_nextval', string="Predicted Number")
    supplier_invoice_number = fields.Char(string='Factura Nº',readonly=True,
                                          #states={'draft': [('readonly', False)]},
                                          copy=False)
    is_of_import = fields.Boolean(string="Is Importation")
    # Vistas/BD pueden referenciar este nombre (libro de compras SAR).
    exclude_from_hn_purchase_book = fields.Boolean(
        string='Excluir compras',
        default=False,
        copy=False,
        help=(
            'Si está activo, la factura se trata como importación: no exige formato SAR ni CAI. '
            'Tampoco se incluye en el DMC ni en el libro de compras.'
        ),
    )
    excluir_importacion = fields.Boolean(
        string='Excluir importación',
        default=False,
        copy=False,
        help=(
            'Si está activo, la factura de proveedor no se incluye en el DMC ni en el libro de compras.'
        ),
    )
    # Referenciado en vistas SAR, DMC y libro compras tesorería.
    excluir_compra = fields.Boolean(
        string='Gasto DMC',
        default=False,
        copy=False,
        help=(
            'Si está activo: en el archivo DMC el total de la factura se clasifica como gasto '
            '(columna monto gasto) y no como costo; y la factura no se incorpora al libro de '
            'compras tesorería (modelo libro compras) al generar sus líneas desde facturas.'
        ),
    )
    cai_shot_compras = fields.Char(string='CAI Compras', copy=False)
    rtn = fields.Char(string="RTN",compute="_get_rtn",store=True)
    check_open_invoice = fields.Integer(
        compute='_compute_open_partner_documents',
        string="Check Open Invoice",
    )
    check_open_bill = fields.Integer(
        compute='_compute_open_partner_documents',
        string="Check Open Bills",
    )
    show_message = fields.Boolean(string="Show Message", compute="show_message_invoice")
    view_name = fields.Boolean(string="Mostrar nombre", compute="_get_view_name")
    view_draft = fields.Boolean(string="Mostrar nombre borrador", compute="_get_view_name")
    add_invoice_attachment = fields.Boolean(
        string='Adjuntar Documento',
        compute='_compute_purchase_order_from_sale_order',
    )
    supplier_invoice_attachment = fields.Binary(string='Factura Proveedor', attachment=True)
    invoice_payments_ids = fields.Char('')
    purchase_order_attachment = fields.Binary(
        string='Archivo Orden de Compra',
        attachment=True,
        compute='_compute_purchase_order_from_sale_order',
    )
    purchase_order_number = fields.Char(
        string="Orden de Compra",
        compute='_compute_purchase_order_from_sale_order',
    )

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move, vals in zip(moves, vals_list):
            if (
                move.move_type in ("in_invoice", "in_refund", "in_receipt")
                and not move.supplier_invoice_number
            ):
                origin = vals.get("invoice_origin") or move.invoice_origin
                if origin:
                    order = (
                        self.env["purchase.order"]
                        .search([("name", "=", origin)], limit=1)
                    )
                    if order and order.vendor_invoice_number:
                        move.supplier_invoice_number = order.vendor_invoice_number
        return moves
    @api.depends('name', 'move_type', 'posted_before', 'quick_edit_mode', 'state')
    def _get_view_name(self):
        for rec in self:
            if rec.move_type in ['out_invoice', 'out_refund', 'out_receipt', 'entry'] and not (rec.name == '/' and not rec.posted_before and not rec.quick_edit_mode):
                rec.view_name = True
            else:
                rec.view_name = False
            if rec.move_type in ['out_invoice', 'out_refund', 'out_receipt', 'entry']:
                rec.view_draft = rec.state == 'draft' and rec.name == '/' and not rec.posted_before and not rec.quick_edit_mode
            else:
                rec.view_draft = False

    @api.depends('invoice_origin')
    def _compute_purchase_order_from_sale_order(self):
        origins = list({o for o in self.mapped('invoice_origin') if o})
        sale_orders = (
            self.env["sale.order"].sudo().search([("name", "in", origins)])
            if origins
            else self.env["sale.order"]
        )
        origin_to_so = {so.name: so for so in sale_orders}
        for rec in self:
            # Asignar siempre los 3 campos del mismo compute (evita ValueError
            # por invalidación de caché al escribir campos no computados).
            rec.purchase_order_number = ""
            rec.add_invoice_attachment = False
            rec.purchase_order_attachment = False
            if not rec.invoice_origin:
                continue
            sale_order = origin_to_so.get(rec.invoice_origin)
            if not sale_order:
                continue
            rec.purchase_order_number = (
                sale_order.purchase_order_number or sale_order.client_order_ref or ""
            )
            rec.add_invoice_attachment = bool(sale_order.add_invoice_attachment)
            if sale_order.add_invoice_attachment:
                rec.purchase_order_attachment = sale_order.purchase_order_attachment

    def print_debit_note_report(self):
        print('')
    def print_credit_note_report(self):
        print('')
    @api.depends('move_type','check_open_bill','check_open_invoice')
    def show_message_invoice(self):
        for rec in self:
            if rec.move_type != 'entry':
                if rec.check_open_invoice == 0 and rec.check_open_bill == 0:
                    rec.show_message = False
                else:
                    rec.show_message = True
            else:
                rec.show_message = False

    @api.depends('partner_id', 'company_id')
    def _compute_open_partner_documents(self):
        """Una sola consulta para facturas y facturas de proveedor abiertas del contacto."""
        counts = {}
        partners = [partner.id for partner in self.partner_id if partner]
        companies = [company.id for company in self.company_id if company]
        if partners and companies:
            rows = self.env['account.move']._read_group(
                [
                    ('partner_id', 'in', partners),
                    ('company_id', 'in', companies),
                    ('state', '=', 'posted'),
                    ('payment_state', '=', 'not_paid'),
                    ('move_type', 'in', ('out_invoice', 'in_invoice')),
                ],
                ['partner_id', 'company_id', 'move_type'],
                ['__count'],
            )
            for partner, company, move_type, count in rows:
                counts[(partner.id, company.id, move_type)] = count
        for rec in self:
            base = (rec.partner_id.id, rec.company_id.id)
            rec.check_open_invoice = counts.get((*base, 'out_invoice'), 0)
            rec.check_open_bill = counts.get((*base, 'in_invoice'), 0)

    def _compute_tax_totals(self):
        """Evita que mostrar los impuestos reescriba las líneas de la factura.

        El cálculo estándar muta el diccionario de tax_totals después de
        asignarlo. Eso dispara el inverse y sincroniza líneas de pago e
        impuestos solo por abrir el formulario.
        """
        with self._disable_recursion(None, 'skip_invoice_sync'):
            super()._compute_tax_totals()

    @api.depends('partner_id')
    def _get_rtn(self):
        for rec in self:
            rec.rtn = rec.partner_id.rtn

    @api.constrains('supplier_invoice_number')
    def _check_unique_supplier_invoice_number_insensitive(self):
        """
        Check if an other vendor bill has the same supplier_invoice_number
        and the same commercial_partner_id than the current instance
        """
        if self.supplier_invoice_number and\
            self.move_type in ('in_invoice', 'in_refund'):
            same_supplier_inv_num = self.search([
                ('commercial_partner_id', '=', self.commercial_partner_id.id),
                ('move_type', 'in', ('in_invoice', 'in_refund')),
                ('supplier_invoice_number',
                 '=ilike', self.supplier_invoice_number),
                ('id', '!=', self.id)
            ], limit=1)
            if same_supplier_inv_num:
                raise ValidationError(_(
                    "The invoice/refund with supplier invoice number '%s' "
                    "already exists in Odoo for supplier '%s'.") % (
                        same_supplier_inv_num.supplier_invoice_number,
                        same_supplier_inv_num.partner_id.display_name))

            # Check the format for the invoice supplier number
            if (
                not re.match(r'^\d{3}-\d{3}-\d{2}-\d{8}$', self.supplier_invoice_number)
                and not self._hn_skip_supplier_sar()
            ):
                raise ValidationError('El formato de la factura ingresada no es válido, este debe seguir un formato válido de la SAR, ejemplo: 000-000-00-00000000')

    @api.onchange('supplier_invoice_number')
    def _onchange_supplier_invoice_number(self):
        self.ref = self.supplier_invoice_number

    @api.depends('move_type', 'debit_origin_id')
    def _get_predict_nextval(self):
        for rec in self:
            if rec.name != '/':
                rec.predict_next_number = ''
                continue
            if not rec.journal_id:
                rec.predict_next_number = ''
                continue

            # Usar el mismo método que se usa para generar el número real de la factura
            sequence_id = rec._get_sequence()
            if sequence_id:
                # Obtener la secuencia actual considerando rangos de fechas
                current_sequence = sequence_id._get_current_sequence()
                if current_sequence:
                    # Usar get_next_char para obtener el siguiente número
                    number = current_sequence.with_context({
                        'ir_sequence_date': rec.invoice_date or fields.Date.today()
                    }).get_next_char(current_sequence.number_next_actual)
                    rec.predict_next_number = number
                else:
                    rec.predict_next_number = ''
            else:
                rec.predict_next_number = ''
    

    def _l10n_hn_sar_validation_before_post(self):
        """SAR/CAI antes de publicar. Un asiento; compatible con publicación en lote (bank, etc.)."""
        self.ensure_one()
        if not self._hn_skip_supplier_sar():
            if not self.partner_id.multiple_cais:
                if self.move_type == 'in_invoice':
                    if not self.partner_id.cai_expires_shot or not self.partner_id.max_number_shot or not self.partner_id.min_number_shot or not self.cai_shot:
                        raise ValidationError(_('Debe definir un CAI de proveedor, fecha de expiración y valor maximo y minimo'))
                    if self.invoice_date:
                        invoice_date = self.invoice_date
                    else:
                        invoice_date = datetime.now().date()
                    if invoice_date > self.partner_id.cai_expires_shot:
                        raise UserError(_('La fecha de expiracion para CAI de proveedor para esta secuencia es %s ') % (self.partner_id.cai_expires_shot) )
                    if self.supplier_invoice_number:
                        sequence_range_limit = False
                        wrong_prefix = False
                        try:
                            actual_number = self.supplier_invoice_number.split('-')[-1:][0]
                            partner_number_min = self.partner_id.min_number_shot.split('-')[-1:][0]
                            partner_number_max = self.partner_id.max_number_shot.split('-')[-1:][0]
                            partner_prefix = self.partner_id.min_number_shot.split('-')[:-1]
                            partner_prefix = "-".join(partner_prefix)
                            actual_prefix = self.supplier_invoice_number.split('-')[:-1]
                            actual_prefix = "-".join(actual_prefix)
                            if partner_prefix != actual_prefix:
                                wrong_prefix = True
                            if int(actual_number) > int(partner_number_max) or int(actual_number) < int(partner_number_min):
                                sequence_range_limit = True
                        except:
                            raise UserError("Some issue with supplier invoice number or Validator SAR numbers!")
                        if wrong_prefix:
                            raise UserError("Partner SAR prefix not match with actual bill's prefix!")
                        if sequence_range_limit:
                            raise UserError(_('La secuencia no esta dentro del rango establecido en el CAI de proveedor'))
                    # Vista «CAI», libro compras (`report_libro_compras_xls`) y DMC leen `cai_shot_compras`; no bastaba el onchange UI.
                    self.cai_shot_compras = (self.partner_id.cai_shot or '').strip()
            else:
                # Multiple CAIs Validations
                valid_cai = None
                if self.move_type not in ['out_invoice', 'out_refund', 'out_receipt','entry']:
                    cai_lines = self.partner_id.supplier_cai_ids.filtered(lambda x: x.active_supplier_cai == True)
                    cai_shots = cai_lines.mapped('supplier_cai_shot')
                    cai_expires_shots = cai_lines.mapped('supplier_cai_expires_shot')
                    min_number_shots = cai_lines.mapped('supplier_min_number_shot')
                    max_number_shots = cai_lines.mapped('supplier_max_number_shot')
                    if not cai_expires_shots or not max_number_shots or not min_number_shots or not cai_shots:
                        raise ValidationError(_('Debe definir al menos un CAI de proveedor, fecha de expiración y valor maximo y minimo'))
                    if self.invoice_date:
                        invoice_date = self.invoice_date
                    else:
                        invoice_date = datetime.now().date()

                    # Find a valid CAI inside the CAI lines
                    if self.supplier_invoice_number:
                        
                        for cai in cai_lines:
                            try:
                                sequence_range_limit = False
                                wrong_prefix = False
                                actual_number = self.supplier_invoice_number.split('-')[-1:][0]
                                partner_number_min = cai.supplier_min_number_shot.split('-')[-1:][0]
                                partner_number_max = cai.supplier_max_number_shot.split('-')[-1:][0]
                                actual_prefix = self.supplier_invoice_number.split('-')[:-1]
                                actual_prefix = "-".join(actual_prefix)
                                if cai.supplier_prefix != actual_prefix:
                                    wrong_prefix = True
                                if int(actual_number) > int(partner_number_max) or int(actual_number) < int(partner_number_min):
                                    sequence_range_limit = True
                                if not wrong_prefix and not sequence_range_limit:
                                    valid_cai = cai
                                    break
                            except:
                                raise UserError("Some issue with supplier invoice number or Validator SAR numbers!")

                        if wrong_prefix and not valid_cai:
                            raise UserError("Partner SAR prefix not match with actual bill's prefix!")
                        if sequence_range_limit and not valid_cai:
                            raise UserError(_('Ninguna secuencia esta dentro del rango establecido en el CAI de proveedor'))
                        if valid_cai:
                            if invoice_date > valid_cai.supplier_cai_expires_shot:
                                raise UserError(_('La Fecha establecida excede la fecha de expiración del CAI: %s' % valid_cai.supplier_cai_shot) )
                            self.cai_invoice = valid_cai.supplier_cai_shot
                            self.cai_shot_compras = valid_cai.supplier_cai_shot
                            self.cai_expires_shot = valid_cai.supplier_cai_expires_shot
                            self.min_number_shot = valid_cai.supplier_prefix+"-"+valid_cai.supplier_min_number_shot
                            self.max_number_shot = valid_cai.supplier_prefix+"-"+valid_cai.supplier_max_number_shot  

            # Detectar si es una nota de débito
            is_debit_note = hasattr(self, 'debit_origin_id') and self.debit_origin_id
            
            # Lógica para facturas de cliente (excluyendo notas de débito)
            if self.journal_id.sequence_id.fiscal_regime and self.move_type in ['out_invoice', 'out_receipt','entry'] and not is_debit_note:
                if not self.journal_id.sequence_id.expiration_date:
                    raise UserError(_('La secuencia para este diario no tiene fecha de expiración') )

                date = self.invoice_date or datetime.today().date()
                if date:
                    if date > self.journal_id.sequence_id.expiration_date:
                        self.journal_id.sequence_id.number_next_actual = self.journal_id.sequence_id.number_next_actual - 1
                        raise UserError(_('la fecha de expiracion para esta secuencia es %s ') % (self.journal_id.sequence_id.expiration_date) )

                max_number = self.journal_id.sequence_id.fiscal_regime.filtered(lambda r: r.selected == True).hasta
                
                if self.journal_id.sequence_id.l_number_next_actual > max_number and not self.name:
                    raise UserError(_('El rango del CAI a excedido por favor configurar uno nuevo') )
                self.cai_invoice = ''

                for regimen in self.journal_id.sequence_id.fiscal_regime:
                    if regimen.selected:
                        if regimen.cai and regimen.cai.sequence_exceed_limit and self.journal_id.sequence_id.max_value and self.journal_id.sequence_id.l_number_next_actual:
                            seq_gap = self.journal_id.sequence_id.max_value + 1 - \
                                    self.journal_id.sequence_id.l_number_next_actual
                            if seq_gap <= regimen.cai.sequence_exceed_limit:
                                self.journal_id.sequence_id.send_sequence_limit_email()
                        self.cai_invoice = regimen.cai.name
                        self.cai_expires_shot = regimen.cai.expiration_date
                        self.min_number_shot = self.journal_id.sequence_id.dis_min_value
                        self.max_number_shot = self.journal_id.sequence_id.dis_max_value

            if self.move_type in ['out_refund']:
                if self.journal_id.refund_sequence_id.fiscal_regime and not self.partner_id.multiple_cais:
                    if not self.journal_id.refund_sequence_id.expiration_date:
                        raise UserError(_('La secuencia de credito para este diario no tiene fecha de expiración') )

                    date = self.invoice_date or datetime.today().date()
                    if date:
                        if date > self.journal_id.refund_sequence_id.expiration_date:
                            self.journal_id.refund_sequence_id.number_next_actual = self.journal_id.refund_sequence_id.number_next_actual - 1
                            raise UserError(_('la fecha de expiracion para esta secuencia de credito es %s ') % (self.journal_id.refund_sequence_id.expiration_date) )

                    max_number = self.journal_id.refund_sequence_id.fiscal_regime.filtered(lambda r: r.selected == True).hasta
                    
                    if self.journal_id.refund_sequence_id.l_number_next_actual > max_number:
                        raise UserError(_('El rango del CAI a excedido por favor configurar uno nuevo') )
                    self.cai_invoice = ''

                    for regimen in self.journal_id.refund_sequence_id.fiscal_regime:
                        if regimen.selected:
                            if regimen.cai and regimen.cai.sequence_exceed_limit and self.journal_id.refund_sequence_id.max_value and self.journal_id.refund_sequence_id.l_number_next_actual:
                                seq_gap = self.journal_id.refund_sequence_id.max_value + 1 - \
                                        self.journal_id.refund_sequence_id.l_number_next_actual
                                if seq_gap <= regimen.cai.sequence_exceed_limit:
                                    self.journal_id.refund_sequence_id.send_sequence_limit_email()
                            self.cai_invoice = regimen.cai.name
                            self.cai_expires_shot = regimen.cai.expiration_date
                            self.min_number_shot = self.journal_id.refund_sequence_id.dis_min_value
                            self.max_number_shot = self.journal_id.refund_sequence_id.dis_max_value

            # Lógica para notas de débito
            if is_debit_note and self.journal_id.debit_sequence_id and self.journal_id.debit_sequence_id.fiscal_regime and not self.partner_id.multiple_cais:
                if not self.journal_id.debit_sequence_id.expiration_date:
                    raise UserError(_('La secuencia de débito para este diario no tiene fecha de expiración') )

                date = self.invoice_date or datetime.today().date()
                if date:
                    if date > self.journal_id.debit_sequence_id.expiration_date:
                        self.journal_id.debit_sequence_id.number_next_actual = self.journal_id.debit_sequence_id.number_next_actual - 1
                        raise UserError(_('la fecha de expiracion para esta secuencia de débito es %s ') % (self.journal_id.debit_sequence_id.expiration_date) )

                max_number = self.journal_id.debit_sequence_id.fiscal_regime.filtered(lambda r: r.selected == True).hasta
                
                if self.journal_id.debit_sequence_id.l_number_next_actual > max_number:
                    raise UserError(_('El rango del CAI a excedido por favor configurar uno nuevo') )
                self.cai_invoice = ''

                for regimen in self.journal_id.debit_sequence_id.fiscal_regime:
                    if regimen.selected:
                        if regimen.cai and regimen.cai.sequence_exceed_limit and self.journal_id.debit_sequence_id.max_value and self.journal_id.debit_sequence_id.l_number_next_actual:
                            seq_gap = self.journal_id.debit_sequence_id.max_value + 1 - \
                                    self.journal_id.debit_sequence_id.l_number_next_actual
                            if seq_gap <= regimen.cai.sequence_exceed_limit:
                                self.journal_id.debit_sequence_id.send_sequence_limit_email()
                        self.cai_invoice = regimen.cai.name
                        self.cai_expires_shot = regimen.cai.expiration_date
                        self.min_number_shot = self.journal_id.debit_sequence_id.dis_min_value
                        self.max_number_shot = self.journal_id.debit_sequence_id.dis_max_value

    def _l10n_hn_backfill_resolve_cai_shot_compras(self):
        """Calcula CAI compras para facturas donde `cai_shot_compras` está vacío.
        Prioridad: campo `cai_invoice` (p. ej. varios CAI en versiones previas); luego proveedor /
        tabla `supplier.cai` igual que validación público / onchange.
        """
        self.ensure_one()
        if self.move_type not in ('in_invoice', 'in_refund', 'in_receipt'):
            return False
        if self._hn_skip_supplier_sar():
            return False

        cached = (self.cai_invoice or '').strip()
        if cached:
            return cached

        partner = self.partner_id
        if not partner:
            return False

        single = (partner.cai_shot or '').strip()

        if not partner.multiple_cais:
            return single or False

        si = self.supplier_invoice_number
        inv_date = self.invoice_date
        if not si or not inv_date:
            return single or False

        parts = si.split('-')
        if len(parts) < 2:
            return single or False
        try:
            invoice_number = int(parts[-1])
        except ValueError:
            return single or False
        pref = '-'.join(parts[:-1])
        matching = partner.supplier_cai_ids.filtered(
            lambda c, p=pref: getattr(c, 'active_supplier_cai', False) and (c.supplier_prefix or '').strip() == p
        )
        for cai in matching:
            exp = getattr(cai, 'supplier_cai_expires_shot', False)
            if exp and exp < inv_date:
                continue
            try:
                min_shot = int(cai.supplier_min_number_shot)
                max_shot = int(cai.supplier_max_number_shot)
            except (TypeError, ValueError):
                continue
            if min_shot <= invoice_number <= max_shot:
                return (cai.supplier_cai_shot or '').strip() or False

        return single or False

    def l10n_hn_action_backfill_cai_shot_compras_selected(self):
        """Lista / acción servidor: facturas seleccionadas con CAI vacío."""
        moves = self.filtered(
            lambda m: m.move_type in ('in_invoice', 'in_refund', 'in_receipt')
            and m.state == 'posted'
            and not (m.cai_shot_compras or '').strip()
        )
        Move = self.env['account.move']
        if not moves:
            summary = _('Ningún registro de la selección aplicaba '
                        '(solo facturas de proveedor publicadas con CAI compras vacío).')
            return Move._l10n_hn_backfill_cai_client_notification({
                'updated': 0,
                'unresolved': 0,
                'unchanged': len(self.filtered(lambda m: (m.cai_shot_compras or '').strip())),
                'skipped': len(self),
                'skipped_import': 0,
                'message': summary,
            })
        result = Move._l10n_hn_backfill_cai_shot_compras_run(moves)
        return Move._l10n_hn_backfill_cai_client_notification(result)

    @api.model
    def _l10n_hn_backfill_cai_shot_compras_run(self, moves):
        """Escribe CAI en `moves`; devuelve diccionario con contadores y texto para notificación."""
        updated = unresolved = unchanged = skipped = 0
        skipped_import = 0
        todo = moves
        for move in todo:
            if (move.cai_shot_compras or '').strip():
                unchanged += 1
                continue
            if move.move_type not in ('in_invoice', 'in_refund', 'in_receipt'):
                skipped += 1
                continue
            if move.state != 'posted':
                skipped += 1
                continue
            if move._hn_skip_supplier_sar():
                skipped_import += 1
                continue
            val = move._l10n_hn_backfill_resolve_cai_shot_compras()
            if not val:
                unresolved += 1
                continue
            move.with_context(skip_readonly_check=True).write({'cai_shot_compras': val})
            updated += 1

        total = updated + unresolved + unchanged + skipped + skipped_import
        summary = _(
            'Revisadas: %(total)s. Actualizadas: %(upd)s. Sin CAI resoluble: %(un)s. '
            'Ya tenían CAI: %(ok)s. Omitidas (tipo/estado): %(sk)s. '
            'Omitidas importación o excluir compras: %(im)s.'
        ) % {
            'total': total,
            'upd': updated,
            'un': unresolved,
            'ok': unchanged,
            'sk': skipped,
            'im': skipped_import,
        }
        message = summary
        return {
            'updated': updated,
            'unresolved': unresolved,
            'unchanged': unchanged,
            'skipped': skipped,
            'skipped_import': skipped_import,
            'message': message,
        }

    @api.model
    def _l10n_hn_backfill_cai_client_notification(self, data):
        unresolved = data.get('unresolved', 0) or 0
        updated = data.get('updated', 0) or 0
        if unresolved:
            notif_type = 'warning'
        elif updated:
            notif_type = 'success'
        else:
            notif_type = 'info'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('CAI compras'),
                'message': data['message'],
                'type': notif_type,
                'sticky': True,
            },
        }


    def _hn_skip_supplier_sar(self):
        """Importación o «Excluir compras»: no exigen formato SAR ni CAI de proveedor."""
        self.ensure_one()
        return bool(self.is_of_import or self.exclude_from_hn_purchase_book)

    @api.model
    def _hn_purchase_report_exclusion_domain(self):
        """Facturas que no entran al DMC ni al libro de compras."""
        return [
            ('exclude_from_hn_purchase_book', '=', False),
            ('excluir_importacion', '=', False),
        ]

    @api.onchange(
        'move_type', 'partner_id', 'supplier_invoice_number', 'invoice_date',
        'is_of_import', 'exclude_from_hn_purchase_book',
    )
    def onchange_partner_id_cai_compras(self):
        """CAI de compras según configuración del proveedor (módulo clásico libro de compras)."""
        self.ensure_one()
        if self._hn_skip_supplier_sar():
            self.cai_shot_compras = False
            return
        if self.move_type == 'out_invoice' or not self.partner_id:
            return
        previous_cai = self.cai_shot_compras
        warning_msg = False
        partner = self.partner_id

        if not partner.multiple_cais:
            self.cai_shot_compras = partner.cai_shot or ''
            return

        if not self.supplier_invoice_number:
            return

        invoice_parts = self.supplier_invoice_number.split('-')
        invoice_number = None
        if len(invoice_parts) < 2:
            warning_msg = _('El número de factura del proveedor no tiene un formato válido.')
            self.cai_shot_compras = previous_cai
        else:
            invoice_number_info = '-'.join(invoice_parts[:-1])
            try:
                invoice_number = int(invoice_parts[-1])
            except ValueError:
                warning_msg = _('El correlativo de la factura del proveedor debe ser numérico.')
                self.cai_shot_compras = previous_cai
            if invoice_number is not None:
                matching_cais = partner.supplier_cai_ids.filtered(
                    lambda c, p=invoice_number_info: c.supplier_prefix == p
                )
                if not matching_cais:
                    warning_msg = _('No hay CAI activos para este proveedor.')
                    self.cai_shot_compras = previous_cai
                elif not self.invoice_date:
                    warning_msg = _('Debe establecer la fecha de factura antes de calcular el CAI.')
                    self.cai_shot_compras = previous_cai
                else:
                    cai_found = False
                    for cai in matching_cais:
                        expiry_date = cai.supplier_cai_expires_shot
                        if expiry_date and expiry_date < self.invoice_date:
                            continue
                        try:
                            min_shot = int(cai.supplier_min_number_shot)
                            max_shot = int(cai.supplier_max_number_shot)
                        except (TypeError, ValueError):
                            continue
                        if min_shot <= invoice_number <= max_shot:
                            self.cai_shot_compras = cai.supplier_cai_shot
                            cai_found = True
                            break
                    if not cai_found and not warning_msg:
                        warning_msg = _(
                            'No hay CAI activos para este proveedor dentro del rango establecido.'
                        )
                        self.cai_shot_compras = previous_cai

        if warning_msg:
            return {
                'warning': {'title': _('Advertencia de CAI'), 'message': warning_msg}
            }

    def action_post(self):
        for move in self:
            if move.move_type in ('out_invoice', 'in_invoice') and move.amount_total == 0:
                raise UserError(_(
                    'No se puede validar una factura de cliente o proveedor con monto total 0.'
                ))
        for move in self:
            move._l10n_hn_sar_validation_before_post()
        for move in self:
            if (
                move.move_type in ("in_invoice", "in_refund", "in_receipt")
                and not move.supplier_invoice_number
            ):
                raise ValidationError(_('Debe ingresar el número de factura del proveedor.'))
        return super(AccountMove, self).action_post()

    def unlink(self):
        for move in self:
            if move.posted_before and not self.env.context.get('force_delete'):
                if not self.env.user.has_group('account.group_account_manager'):
                    raise UserError(_("You cannot delete an entry which has been posted once."))
        moves = self
        if any(move.posted_before for move in self) and self.env.user.has_group(
            'account.group_account_manager',
        ):
            moves = self.with_context(force_delete=True)
        return super(AccountMove, moves).unlink()
