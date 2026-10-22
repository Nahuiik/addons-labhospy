# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields, models
from odoo.tools.safe_eval import safe_eval


class IrFilters(models.Model):
    _inherit = 'ir.filters'

    sequence = fields.Integer(default=10)

    _order = 'model_id, sequence, name, id desc'

    def get_filters(self, model, action_id=None, embedded_action_id=None, embedded_parent_res_id=None):
        filters = super().get_filters(model, action_id=action_id, embedded_action_id=embedded_action_id,
                                      embedded_parent_res_id=embedded_parent_res_id)
        today = fields.Date.context_today(self)
        token_map = {
            '__TODAY__': fields.Date.to_string(today),
            '__YESTERDAY__': fields.Date.to_string(today - timedelta(days=1)),
            '__TOMORROW__': fields.Date.to_string(today + timedelta(days=1)),
            '__WEEK_START__': fields.Date.to_string(today - timedelta(days=today.weekday())),
            '__WEEK_NEXT_START__': fields.Date.to_string(today - timedelta(days=today.weekday()) + timedelta(days=7)),
        }
        for filter_data in filters:
            domain_str = filter_data.get('domain')
            if not domain_str:
                continue
            try:
                domain = safe_eval(domain_str)
            except Exception:
                continue
            processed = self._replace_dynamic_tokens(domain, token_map)
            filter_data['domain'] = repr(processed)
        return filters

    def _replace_dynamic_tokens(self, value, token_map):
        if isinstance(value, str):
            return token_map.get(value, value)
        if isinstance(value, list):
            return [self._replace_dynamic_tokens(item, token_map) for item in value]
        if isinstance(value, tuple):
            return tuple(self._replace_dynamic_tokens(item, token_map) for item in value)
        return value
