# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _gn_get_invoice_report_partner(self):
        """Socio que debe figurar en el PDF de factura / nota de crédito (cliente)."""
        self.ensure_one()
        if self.move_type not in ('out_invoice', 'out_refund'):
            return self.partner_id
        commercial = self.partner_id.commercial_partner_id
        if not commercial:
            return self.partner_id
        if commercial.gn_is_patient and not commercial._gn_has_fiscal_rtn():
            try:
                return self.env.ref('gn_discount_fiscal.partner_consumidor_final').sudo()
            except ValueError:
                return self.partner_id
        return self.partner_id

    def _gn_invoice_print_contact_name_line(self):
        """
        Texto adicional en PDF cuando el encabezado fiscal es CONSUMIDOR FINAL:
        muestra el nombre real del paciente/contacto.
        """
        self.ensure_one()
        if self.move_type not in ('out_invoice', 'out_refund'):
            return False
        commercial = self.partner_id.commercial_partner_id
        if not commercial:
            return False
        try:
            cf = self.env.ref('gn_discount_fiscal.partner_consumidor_final').sudo()
        except ValueError:
            return False
        if self._gn_get_invoice_report_partner().id != cf.id:
            return False
        name = (commercial.name or '').strip()
        if not name:
            return False
        return _('Nombre del contacto: %(name)s') % {'name': name}

    gn_fiscal_matrix_notice = fields.Char(
        string='Aviso descuento fiscal',
        compute='_compute_gn_fiscal_matrix_notice',
    )

    @api.depends(
        'move_type',
        'partner_id',
        'partner_id.gn_birthdate',
        'partner_id.gn_is_special_patient',
        'partner_id.is_company',
        'invoice_line_ids.discount',
        'invoice_line_ids.display_type',
    )
    def _compute_gn_fiscal_matrix_notice(self):
        for move in self:
            if move.move_type not in ('out_invoice', 'out_refund'):
                move.gn_fiscal_matrix_notice = False
                continue
            partner = move.partner_id.commercial_partner_id if move.partner_id else False
            if (
                not partner
                or partner.is_company
                or partner.gn_fiscal_discount_percent <= 0
            ):
                move.gn_fiscal_matrix_notice = False
                continue
            has_line_discount = any(
                line.discount and line.display_type == 'product'
                for line in move.invoice_line_ids
            )
            if not has_line_discount:
                move.gn_fiscal_matrix_notice = False
                continue
            move.gn_fiscal_matrix_notice = _(
                'Se aplica descuento fiscal según la matriz configurada (%(pct)s%%).'
            ) % {'pct': partner.gn_fiscal_discount_percent}
