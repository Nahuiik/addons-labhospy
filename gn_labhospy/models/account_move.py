from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def _gn_labhospy_enforce_receipt_resolution(self):
        """Si es False, no se exige resolución al validar albaranes ni al publicar facturas de compra."""
        value = self.env['ir.config_parameter'].sudo().get_param(
            'gn_labhospy.enforce_resolution_on_receipt', 'False',
        )
        return str(value).lower() in ('1', 'true', 'yes')

    gn_labhospy_sc_contact_id = fields.Many2one(
        'res.partner',
        string='Contacto (sustancias controladas)',
        domain="['|', ('id', '=', commercial_partner_id), '&', ('parent_id', '=', commercial_partner_id), ('type', '=', 'contact')]",
        help='Persona de contacto (registro hijo tipo «Contacto»); su nombre aparece en el informe SC.',
    )
    gn_labhospy_has_sc_lines = fields.Boolean(
        compute='_compute_gn_labhospy_has_sc_lines',
    )
    gn_labhospy_es_importacion = fields.Boolean("Es importación")

    @api.depends(
        'invoice_line_ids.product_id',
        'invoice_line_ids.product_id.product_tmpl_id.gn_labhospy_is_controlled',
        'invoice_line_ids.display_type',
    )
    def _compute_gn_labhospy_has_sc_lines(self):
        for move in self:
            prod_lines = move.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product' and l.product_id
            )
            move.gn_labhospy_has_sc_lines = any(
                line.product_id.product_tmpl_id.gn_labhospy_is_controlled
                for line in prod_lines
            )

    @api.onchange('partner_id')
    def _onchange_partner_id_gn_labhospy_sc_contact(self):
        if not self.partner_id or self.gn_labhospy_sc_contact_id:
            return
        comm = self.partner_id.commercial_partner_id
        if comm.is_company:
            child = self.env['res.partner'].search([
                ('parent_id', '=', comm.id),
                ('type', '=', 'contact'),
            ], limit=1)
            self.gn_labhospy_sc_contact_id = child
        else:
            self.gn_labhospy_sc_contact_id = comm

    def _gn_labhospy_invoice_address_partner(self):
        """Dirección sobre la cual se emitió la factura (partner_id), no la de entrega."""
        self.ensure_one()
        return self.partner_id

    def _gn_labhospy_sc_report_contact_name(self):
        """Nombre de la persona de contacto (hijo), nunca el de la institución."""
        self.ensure_one()
        comm = self.commercial_partner_id

        contact = self.gn_labhospy_sc_contact_id
        if contact and not contact.is_company:
            if contact.parent_id == comm or (comm and not comm.is_company and contact == comm):
                return (contact.name or '').strip()

        partner = self.partner_id
        if partner and not partner.is_company:
            return (partner.name or '').strip()

        if comm and comm.is_company:
            child = self.env['res.partner'].search([
                ('parent_id', '=', comm.id),
                ('type', '=', 'contact'),
                ('is_company', '=', False),
            ], limit=1, order='id asc')
            if child:
                return (child.name or '').strip()

        return ''

    def _gn_labhospy_sc_report_partner_address(self, partner=None):
        """Dirección de facturación del cliente sin el nombre de la empresa."""
        self.ensure_one()
        partner = partner or self._gn_labhospy_invoice_address_partner()
        if not partner:
            return ''
        return (partner._display_address(without_company=True) or '').replace('\n', ', ').strip()

    def _gn_labhospy_partner_address_complete(self, partner):
        if not partner:
            return False
        street_ok = bool(partner.street and partner.street.strip())
        city_ok = bool(
            (partner.city and partner.city.strip())
            or partner.city_id
        )
        country_ok = bool(partner.country_id)
        return street_ok and city_ok and country_ok

    def _gn_labhospy_should_skip_sc_invoice_validation(self):
        """Omitir validación SC en facturas cliente (p. ej. validador SAR)."""
        if self.env.context.get('gn_labhospy_skip_sc_invoice_validation'):
            return True
        return self.env.user.has_group(
            'l10n_hn_customer_ref_invoice.group_customer_ref_invoice_post',
        )

    def _gn_labhospy_collect_sc_invoice_errors(self):
        """Devuelve lista de mensajes bloqueantes si la factura cliente tiene líneas SC."""
        self.ensure_one()
        if self._gn_labhospy_should_skip_sc_invoice_validation():
            return []
        if self.move_type not in ('out_invoice', 'out_refund'):
            return []
        prod_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product'
            and l.product_id
            and l.product_id.product_tmpl_id.gn_labhospy_is_controlled
        )
        if not prod_lines:
            return []
        msgs = []
        if not self.commercial_partner_id:
            msgs.append(_('Debe indicar la empresa a quien se vende (cliente / dirección de factura).'))
        elif not (self.commercial_partner_id.name or '').strip():
            msgs.append(_('El nombre de la empresa (cliente comercial) es obligatorio para sustancias controladas.'))

        if not self.gn_labhospy_sc_contact_id:
            msgs.append(_('Debe indicar el contacto de sustancias controladas.'))
        else:
            comm = self.commercial_partner_id
            contact = self.gn_labhospy_sc_contact_id
            allowed = contact.id == comm.id or (
                contact.parent_id.id == comm.id and contact.type == 'contact'
            )
            if not allowed:
                msgs.append(_(
                    'El contacto SC debe ser el cliente persona físico o un contacto hijo del cliente.'
                ))

        addr = self._gn_labhospy_invoice_address_partner()
        if not self._gn_labhospy_partner_address_complete(addr):
            msgs.append(_(
                'La dirección de facturación del cliente es obligatoria (calle, ciudad y país) '
                'para sustancias controladas. Revise el contacto configurado en la factura.'
            ))

        missing_use = prod_lines.filtered(
            lambda l: not l.gn_labhospy_application_use_id
            and not (l.gn_labhospy_application_use or '').strip()
        )
        if missing_use:
            names = ', '.join(missing_use.mapped('name')[:5])
            extra = len(missing_use) - 5
            suf = _(' y %(count)s más…') % {'count': extra} if extra > 0 else ''
            msgs.append(
                _('Debe indicar la aplicación de uso (catálogo o texto) en cada línea de sustancia controlada: %s%s')
                % (names, suf)
            )
        return msgs

    def _gn_labhospy_collect_sc_vendor_bill_errors(self):
        """Facturas de proveedor con líneas SC: recepciones validadas con resolución SC."""
        self.ensure_one()
        if self.move_type not in ('in_invoice', 'in_refund'):
            return []
        prod_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product'
            and l.product_id
            and l.product_id.product_tmpl_id.gn_labhospy_is_controlled
        )
        if not prod_lines:
            return []
        msgs = []
        pol_lines = prod_lines.filtered('purchase_line_id')
        orphan = prod_lines - pol_lines
        if orphan:
            msgs.append(_(
                'En facturas de compra con sustancias controladas, cada línea de producto debe estar '
                'vinculada a una línea del pedido de compra (para comprobar la resolución en recepción).'
            ))

        pickings = self.env['stock.picking']
        for line in pol_lines:
            moves = line.purchase_line_id.move_ids.filtered(
                lambda m: m.state == 'done'
                and m.picking_id
                and m.picking_id.picking_type_id.code == 'incoming'
            )
            pickings |= moves.mapped('picking_id')

        if pol_lines and not pickings:
            msgs.append(_(
                'No hay recepciones validadas vinculadas a las líneas de compra de sustancias controladas. '
                'Valide el albarán de entrada; en recepciones SC debe indicarse la resolución antes de validar.'
            ))

        if self._gn_labhospy_enforce_receipt_resolution():
            bad_pickings = pickings.filtered(
                lambda p: p._gn_labhospy_requires_resolution()
                and not (p.gn_labhospy_resolution_ref or '').strip()
            )
            if bad_pickings:
                names = ', '.join(bad_pickings.mapped('name')[:5])
                extra = len(bad_pickings) - 5
                suf = _(' y %(count)s más…') % {'count': extra} if extra > 0 else ''
                msgs.append(
                    _('Resolución SC obligatoria en el albarán de recepción: %s%s') % (names, suf)
                )
        return msgs

    def _gn_labhospy_collect_intl_vendor_bill_errors(self):
        """Facturas de proveedor de importación: recepciones validadas deben tener resolución."""
        self.ensure_one()
        if self.move_type not in ('in_invoice', 'in_refund'):
            return []
        if not getattr(self, 'is_of_import', False):
            return []
        prod_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product' and l.product_id
        )
        if not prod_lines:
            return []
        msgs = []
        pol_lines = prod_lines.filtered('purchase_line_id')
        orphan = prod_lines - pol_lines
        if orphan:
            msgs.append(_(
                'En facturas de compra marcadas como importación, cada línea de producto debe estar '
                'vinculada a una línea del pedido de compra.'
            ))

        pickings = self.env['stock.picking']
        for line in pol_lines:
            moves = line.purchase_line_id.move_ids.filtered(
                lambda m: m.state == 'done'
                and m.picking_id
                and m.picking_id.picking_type_id.code == 'incoming'
            )
            pickings |= moves.mapped('picking_id')

        if pol_lines and not pickings:
            msgs.append(_(
                'No hay recepciones validadas vinculadas a las líneas de compra. '
                'Valide el albarán de entrada indicando la resolución antes de registrar la factura.'
            ))

        if self._gn_labhospy_enforce_receipt_resolution():
            bad_pickings = pickings.filtered(
                lambda p: p._gn_labhospy_requires_resolution()
                and not (p.gn_labhospy_resolution_ref or '').strip()
            )
            if bad_pickings:
                names = ', '.join(bad_pickings.mapped('name')[:5])
                extra = len(bad_pickings) - 5
                suf = _(' y %(count)s más…') % {'count': extra} if extra > 0 else ''
                msgs.append(
                    _('Indique la resolución obligatoria en el albarán de recepción: %s%s') % (names, suf)
                )
        return msgs

    def _post(self, soft=True):
        for move in self:
            errors = move._gn_labhospy_collect_sc_invoice_errors()
            if errors:
                raise UserError('\n'.join(errors))
        return super()._post(soft=soft)
