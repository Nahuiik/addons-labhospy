# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _, api
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    inv_movement_rec_limit = fields.Char(string="Records Limit", default=80, size=9,
            help="Limit the number of records to display on screen at a time.", config_parameter='stock_movement_report.inv_movement_rec_limit')

    @api.constrains('inv_movement_rec_limit')
    def _check_inv_movement_rec_limit(self):
        for obj in self:
            if int(obj.inv_movement_rec_limit) < 0:
                raise ValidationError(_('Record Limit can not be negative.'))
