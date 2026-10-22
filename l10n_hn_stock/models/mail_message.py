# -*- coding: utf-8 -*-
# Part of l10n_hn_stock. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class MailMessage(models.Model):
    _inherit = "mail.message"

    @api.model_create_multi
    def create(self, vals_list):
        messages = super().create(vals_list)
        if self.env.context.get("l10n_skip_product_variant_chatter_replica"):
            return messages
        to_create = []
        IMD = self.env["ir.model.fields"].sudo()
        for msg in messages:
            if msg.model != "product.template" or not msg.res_id:
                continue
            # tracking_value_ids suele estar restringido a administradores; la réplica
            # servidor→variantes no debe exigir ese permiso al usuario que disparó el mensaje.
            msg_sv = msg.sudo()
            if not msg_sv.tracking_value_ids:
                continue
            tmpl = self.env["product.template"].sudo().browse(msg.res_id)
            if not tmpl:
                continue
            tv_vals_list = self._l10n_hn_remap_template_tracking_to_variant(
                msg_sv, IMD
            )
            if not tv_vals_list:
                continue
            for variant in tmpl.product_variant_ids:
                to_create.append(
                    {
                        "model": "product.product",
                        "res_id": variant.id,
                        "body": msg.body,
                        "message_type": msg.message_type,
                        "subtype_id": msg.subtype_id.id,
                        "author_id": msg.author_id.id,
                        "is_internal": msg.is_internal,
                        "date": msg.date,
                        "tracking_value_ids": [
                            (0, 0, tv) for tv in tv_vals_list
                        ],
                    }
                )
        if to_create:
            self.env["mail.message"].with_context(
                l10n_skip_product_variant_chatter_replica=True
            ).create(to_create)
        return messages

    @staticmethod
    def _l10n_hn_remap_template_tracking_to_variant(msg_sv, IMD_sudo):
        """Replica valores de trazado de plantilla hacia el mismo Campo (nombre) en product.product.

        ``msg_sv`` debe ser el mensaje en sudo() para leer ``tracking_value_ids`` sin permisos de admin.
        """
        out = []
        for tv in msg_sv.tracking_value_ids:
            if not tv.field_id:
                continue
            fname = tv.field_id.name
            try:
                pfield = IMD_sudo._get("product.product", fname)
            except ValueError:
                pfield = None
            if not pfield or fname not in msg_sv.env["product.product"]._fields:
                continue
            out.append(
                {
                    "field_id": pfield.id,
                    "field_info": tv.field_info,
                    "old_value_integer": tv.old_value_integer,
                    "old_value_float": tv.old_value_float,
                    "old_value_char": tv.old_value_char,
                    "old_value_text": tv.old_value_text,
                    "old_value_datetime": tv.old_value_datetime,
                    "new_value_integer": tv.new_value_integer,
                    "new_value_float": tv.new_value_float,
                    "new_value_char": tv.new_value_char,
                    "new_value_text": tv.new_value_text,
                    "new_value_datetime": tv.new_value_datetime,
                    "currency_id": (
                        tv.currency_id.id if tv.currency_id else False
                    ),
                }
            )
        return out
