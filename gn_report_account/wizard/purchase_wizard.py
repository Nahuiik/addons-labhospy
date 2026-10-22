# -*- coding: utf-8 -*-
import logging

from odoo import models, api, fields, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class PurchaseWizard(models.TransientModel):
    _name = "gn_report_account.purchase_wizard"
    _description = "Purchase Report Wizard"

    include_payments = fields.Boolean(string="Imprimir Pagos")
    date_from = fields.Date(string="Fecha Inicio")
    date_to = fields.Date(string="Fecha Final")
    admin_percentage = fields.Float(string="Administrativo (%)")
    indirect_cost_percentage = fields.Float(string="Costo indirecto (%)")
    values_in = fields.Selection(
        selection=[("usd", "USD"), ("local_currency", "Local Currency")],
        string="Values in",
        default="local_currency",
    )
    @api.model
    def _selection_report_type(self):
        return [
            ('summary', _('Summary')),
            ('detailed', _('Detailed')),
        ]

    @api.model
    def _selection_state(self):
        return [
            ('not_paid', _('Open')),
            ('paid', _('Paid')),
        ]

    report_type = fields.Selection(
        selection=_selection_report_type,
        string="Report Type",
        default="detailed",
    )
    state = fields.Selection(
        selection=_selection_state,
        string="State",
    )
    type_product = fields.Selection(string='', selection=[('consu', 'Consumable'), ('service', 'Service'),('product','Storable Product')])

    @api.model
    def _auto_init(self):
        self._drop_invalid_selection_columns()
        return super()._auto_init()

    def _drop_invalid_selection_columns(self):
        self.env.cr.execute("SELECT to_regclass(%s)", (self._table,))
        if not self.env.cr.fetchone()[0]:
            return

        self.env.cr.execute(
            """
            SELECT column_name, data_type
              FROM information_schema.columns
             WHERE table_schema = current_schema()
               AND table_name = %s
               AND column_name in ('report_type', 'state')
            """,
            (self._table,),
        )
        rows = self.env.cr.fetchall()
        if not rows:
            return

        invalid = [name for name, dtype in rows if dtype not in ('character varying', 'text')]
        if invalid:
            _logger.warning(
                "Resetting table %s to clear invalid column types for %s",
                self._table,
                ", ".join(invalid),
            )
            self.env.cr.execute('DROP TABLE IF EXISTS "%s" CASCADE' % self._table)

    def export_xls(self):
        """Call when button 'Get Report' clicked."""
        context = self.env.context
        data = {
            'ids': context.get('active_ids', []),
            'date_from': self.date_from,
            'date_to': self.date_to,
            'values_in': self.values_in,
            'report_type': self.report_type,
            'state': self.state,
            'type_product': self.type_product,
            'include_payments': self.include_payments,
            'admin_percentage': self.admin_percentage,
            'indirect_cost_percentage': self.indirect_cost_percentage,
            # Backward compatibility with report helpers
            'per_administrative': self.admin_percentage,
            'per_indirect_cost': self.indirect_cost_percentage,
        }
        data['model'] = 'gn_report_account.purchase_wizard'
        data['form'] = self.read()[0]
        data['form']['per_administrative'] = self.admin_percentage
        data['form']['per_indirect_cost'] = self.indirect_cost_percentage
        data['form']['include_payments'] = self.include_payments
        for field in data['form'].keys():
            if isinstance(data['form'][field], tuple):
                data['form'][field] = data['form'][field][0]
        if not self.include_payments:
            if self.env.context.get('xls_export'):
                return self.env.ref('gn_report_account.action_purchase_report').report_action(self, data=data)
        else:
            if self.env.context.get('xls_export'):
                return self.env.ref('gn_report_account.action_purchase_payments_report').report_action(self, data=data)

    @api.constrains('date_from','date_to')
    def validate_dates(self):
        if self.date_from and self.date_to:
            if self.date_from > self.date_to:
                raise ValidationError(_('The initial date can not be greater than the final.'))
