# -*- coding: utf-8 -*-
"""
Wizard para asociar anticipos a una orden de venta.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class LinkAdvanceWizardLine(models.TransientModel):
    _name = 'link.advance.wizard.line'
    _description = 'Línea de Wizard Asociar Abono/Anticipo'

    wizard_id = fields.Many2one(
        'link.advance.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    payment_id = fields.Many2one(
        'account.payment',
        string='Abono/Anticipo',
        required=False,
        readonly=True,
    )
    payment_date = fields.Date(related='payment_id.date', readonly=True)
    payment_name = fields.Char(related='payment_id.name', readonly=True)
    available_amount = fields.Monetary(
        string='Saldo Disponible',
        currency_field='currency_id',
        readonly=True,
    )
    amount_to_link = fields.Monetary(
        string='Monto a Asociar',
        currency_field='currency_id',
        required=True,
        default=0.0,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='payment_id.currency_id',
        readonly=True,
    )

    @api.constrains('amount_to_link', 'available_amount', 'payment_id')
    def _check_amount(self):
        for line in self:
            if not line.payment_id:
                continue
            if line.amount_to_link < 0:
                raise ValidationError(_('El monto no puede ser negativo.'))
            if line.amount_to_link > line.available_amount:
                raise ValidationError(_(
                    'El monto (%s) no puede exceder el saldo disponible (%s).',
                    line.amount_to_link, line.available_amount
                ))


class LinkAdvanceWizard(models.TransientModel):
    _name = 'link.advance.wizard'
    _description = 'Asociar Abono/Anticipo a Orden de Venta'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        related='sale_order_id.partner_id',
        readonly=True,
    )
    amount_total = fields.Monetary(
        related='sale_order_id.amount_total',
        readonly=True,
    )
    currency_id = fields.Many2one(
        related='sale_order_id.currency_id',
        readonly=True,
    )
    line_ids = fields.One2many(
        'link.advance.wizard.line',
        'wizard_id',
        string='Abonos/Anticipos Disponibles',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        order_id = self.env.context.get('default_sale_order_id') or self.env.context.get('active_id')
        if order_id:
            order = self.env['sale.order'].browse(order_id)
            if order.exists() and order.partner_id and order.company_id:
                Payment = self.env['account.payment']
                advances = Payment._get_available_advances_for_partner(
                    order.partner_id.id,
                    order.company_id.id,
                    order.currency_id.id,
                    partner_type='customer'
                )
                # Excluir anticipos ya asociados a esta orden
                linked_payment_ids = order.advance_link_ids.mapped('payment_id').ids
                advances = advances.filtered(lambda a: a.id not in linked_payment_ids)
                lines = []
                remaining = order.amount_total - order.advance_linked_amount
                for adv in advances:
                    max_link = min(adv.advance_available_amount, remaining)
                    if max_link > 0:
                        lines.append((0, 0, {
                            'payment_id': adv.id,
                            'available_amount': adv.advance_available_amount,
                            'amount_to_link': max_link,
                        }))
                        remaining -= max_link
                        if remaining <= 0:
                            break
                res['line_ids'] = lines
        return res

    def action_confirm(self):
        """Crea los enlaces sale.order.advance.link y distribuye a las cuotas si existen."""
        self.ensure_one()
        # Solo procesar líneas con anticipo y monto > 0 (evita líneas vacías o sin payment_id)
        lines = self.line_ids.filtered(
            lambda l: l.payment_id and l.amount_to_link > 0
        )
        if not lines:
            raise UserError(_('Debe indicar al menos un monto mayor a cero en un Abono/Anticipo.'))
        Link = self.env['sale.order.advance.link']
        for line in lines:
            Link.create({
                'sale_order_id': self.sale_order_id.id,
                'payment_id': line.payment_id.id,
                'amount': line.amount_to_link,
            })
        order = self.sale_order_id
        total_linked = sum(
            link.amount for link in order.advance_link_ids
            if link.currency_id == order.currency_id
        )
        if order.advance_quota_ids and total_linked > 0:
            order._distribute_advances_to_quotas(total_linked)
        elif not order.advance_quota_ids and total_linked > 0:
            order.message_post(
                body=_(
                    'Los Abonos/Anticipos se han asociado pero no hay plan de cuotas. '
                    'Cree el plan de cuotas (Generar cuotas) y use "Asociar automáticamente" '
                    'para distribuir los Abonos/Anticipos a las cuotas.'
                ),
                message_type='notification',
            )
        return {'type': 'ir.actions.act_window_close'}

    def action_create_quota_plan(self):
        """Abre el wizard para crear el plan de cuotas si no existe."""
        self.ensure_one()
        return {
            'name': _('Generar Plan de Cuotas'),
            'type': 'ir.actions.act_window',
            'res_model': 'generate.quotas.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.sale_order_id.id,
            },
        }
