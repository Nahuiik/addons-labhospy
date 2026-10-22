# -*- coding: utf-8 -*-
# Part of Odoo Module Developed by BrowseInfo.
# See LICENSE file for full copyright and licensing details.

import json

from odoo import api, fields, models


class IrFilters(models.Model):
    _inherit = "ir.filters"

    bi_report_options_json = fields.Text(
        string="Opciones informe BI",
        help="JSON de opciones guardadas para bi_financial_reports_comm (reporte del modelo vinculado).",
    )

    @api.model
    def bi_financial_save_options_filter(self, model_name, name, options):
        """Guarda las opciones actuales del informe como filtro personal."""
        if not name or not str(name).strip():
            return {"error": "empty_name"}
        if not self.env["ir.model"].sudo().search([("model", "=", model_name)], limit=1):
            return {"error": "unknown_model"}
        opts = options if isinstance(options, dict) else {}
        try:
            payload = json.dumps(opts, default=str)
        except (TypeError, ValueError):
            return {"error": "serialize"}
        existing = self.sudo().search(
            [
                ("model_id", "=", model_name),
                ("user_ids", "in", [self.env.uid]),
                ("name", "=", str(name).strip()),
                ("bi_report_options_json", "!=", False),
            ],
            limit=1,
        )
        vals = {
            "name": str(name).strip(),
            "model_id": model_name,
            "user_ids": [(6, 0, [self.env.uid])],
            "action_id": False,
            "domain": "[]",
            "context": "{}",
            "sort": "[]",
            "bi_report_options_json": payload,
        }
        if existing:
            existing.write(vals)
            return {"id": existing.id}
        rec = self.sudo().create(vals)
        return {"id": rec.id}

    @api.model
    def bi_financial_list_saved_filters(self, model_name):
        rows = self.sudo().search_read(
            [
                ("model_id", "=", model_name),
                ("user_ids", "in", [self.env.uid]),
                ("bi_report_options_json", "!=", False),
            ],
            ["id", "name"],
            order="name",
        )
        return rows

    @api.model
    def bi_financial_load_filter(self, filter_id):
        rec = self.sudo().browse(int(filter_id))
        if not rec or not rec.bi_report_options_json:
            return {}
        if self.env.uid not in rec.user_ids.ids:
            return {}
        try:
            return json.loads(rec.bi_report_options_json)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

    @api.model
    def bi_financial_delete_filter(self, filter_id):
        rec = self.sudo().browse(int(filter_id))
        if self.env.uid not in rec.user_ids.ids:
            return False
        rec.unlink()
        return True
