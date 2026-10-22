from __future__ import division
from odoo import models, fields, _, api
from odoo.exceptions import UserError, ValidationError
import time
from lxml.html.builder import INS


class ir_sequence(models.Model):
    _inherit = "ir.sequence"

    @api.depends('min_value')
    def display_min_value(self):
        self.dis_min_value = False
        for rec in self:
            if rec.prefix:
                start_number_filled = str(rec.min_value)
                for relleno in range(len(str(rec.min_value)), rec.padding):
                    start_number_filled = '0'+ start_number_filled
                rec.dis_min_value = rec.prefix + str(start_number_filled)
            else:
                rec.dis_min_value = 0

    @api.depends('max_value')
    def display_max_value(self):
        self.dis_max_value = False
        for rec in self:
            if rec.prefix:
                final_number = rec.max_value
                final_number_filled = str(rec.max_value)
                for relleno in range(len(str(final_number)),rec.padding):
                    final_number_filled = '0'+ final_number_filled
                rec.dis_max_value = rec.prefix + str(final_number_filled)
            else:
                rec.dis_max_value = 0

    fiscal_regime = fields.One2many('dei.fiscal_regime', 'sequence')
    start_date = fields.Date('Start Date')
    expiration_date = fields.Date('Expiration Date', compute="get_expiration_date")
    min_value = fields.Integer("Min Value", compute='get_min_value')
    max_value = fields.Integer("Max Value", compute='get_max_value')
    dis_min_value = fields.Char('min number',readonly=True, compute="display_min_value")
    dis_max_value = fields.Char('max number',readonly=True, compute="display_max_value")
    percentage_alert = fields.Float('percentage alert', default=80)
    # percentage         = fields.Float('percentage' )
    percentage = fields.Float('percentage', compute='compute_percentage')
    l_prefix = fields.Char('prefix', related='prefix')
    l_padding = fields.Integer('Number padding', related='padding')
    l_number_next_actual = fields.Integer('Secuencia Siguiente', related='number_next_actual')

    def send_sequence_limit_email(self):
        """Sending cai expiry notification."""
        user_ids = self.fiscal_regime.cai.notify_user_ids
        email_lst = list(set(user_ids.filtered(
            lambda i: i.email).mapped('email')))
        email_to = ','.join([str(i) for i in email_lst])
        email_values = {'email_to': email_to}
        template_id = self.env.ref(
            'l10n_hn_account.cai_sequence_limit_notify_mail_template')

        mail_id = template_id.send_mail(self.id,
                                        force_send=True,
                                        email_values=email_values)

    def create(self, values):
        new_id = super(ir_sequence, self).create(values)
        self.validar()
        return new_id

    def write(self, values):
        write_id = super(ir_sequence, self).write(values)
        self.validar()
        return write_id

    @api.depends('fiscal_regime')
    def get_expiration_date(self):
        for rec in self:
            if rec.fiscal_regime:
                for regime in rec.fiscal_regime:
                    if regime.selected:
                        rec.expiration_date = regime.cai.expiration_date
                    else:
                        rec.expiration_date = False
                    return
            rec.expiration_date = False

    @api.depends('fiscal_regime')
    def get_min_value(self):
        self.min_value = 0
        for rec in self:
            if rec.fiscal_regime:
                active_fiscal_regime_id = rec.fiscal_regime.filtered(lambda x: x.selected)
                if len(active_fiscal_regime_id) > 1:
                    raise ValidationError(_('You can only select one fiscal regime'))

                rec.min_value = active_fiscal_regime_id.desde


    @api.depends('fiscal_regime')
    def get_max_value(self):
        self.max_value = 0
        for rec in self:
            if rec.fiscal_regime:
                active_fiscal_regime_id = rec.fiscal_regime.filtered(lambda x: x.selected)
                if len(active_fiscal_regime_id) > 1:
                    raise ValidationError(_('You can only select one fiscal regime'))

                rec.max_value = active_fiscal_regime_id.hasta



    @api.depends('number_next_actual')
    def compute_percentage(self):
        for rec in self:
            numerator = rec.number_next_actual - rec.min_value
            denominator = rec.max_value - rec.min_value
            if denominator > 0:
                difference = (rec.number_next_actual - rec.min_value) / (rec.max_value - rec.min_value)
                rec.percentage = (difference * 100) - 1
            else:
                rec.percentage = 0

    def validar(self):
        already_in_list = []
        for fiscal_line in self.fiscal_regime:
            if fiscal_line.cai.name in already_in_list:
                raise UserError(_(' %s this cai is already in use ') % (fiscal_line.cai.name))
            already_in_list.append(fiscal_line.cai.name)

        for fiscal_line in self.fiscal_regime:
            for fiscal_line_compare in self.fiscal_regime:
                if fiscal_line.desde > fiscal_line_compare.desde and fiscal_line.desde < fiscal_line_compare.hasta:
                    raise UserError(_('%s to %s fiscal line overlaps ' ) %(fiscal_line.desde,fiscal_line.hasta))
                if fiscal_line.hasta > fiscal_line_compare.desde and fiscal_line.hasta < fiscal_line_compare.hasta:
                    raise UserError(_('%s to %s fiscal line overlaps ' ) %(fiscal_line.desde,fiscal_line.hasta))

        for fiscal_line in self.fiscal_regime:
            if fiscal_line.desde > fiscal_line.hasta:
                raise UserError(_('min_value %s to max_value %s' ) %(fiscal_line.desde,fiscal_line.hasta))

