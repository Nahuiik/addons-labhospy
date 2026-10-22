# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik - Legacy ISR table for "Establecer ISR" flow

from odoo import api, fields, models


class HrISR(models.Model):
    _name = "hr.isr"
    _description = "ISR (Legacy table for Establecer ISR)"

    def set_isr(self):
        self.write({'state': 'validated'})

    def set_to_draft(self):
        self.write({'state': 'draft'})

    name = fields.Char("Descripción", required=True)
    pay_periodicity = fields.Selection([
        ('weekly', 'Semanal'),
        ('bi-weekly', 'Quincenal'),
        ('monthly', 'Mensual'),
    ], "Periodicidad Pago", default='bi-weekly')
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('validated', 'Validado'),
    ], "Estado", default='draft')
    exempt_salary = fields.Float("Salario Exento")
    medical_expense = fields.Float("Gastos Médicos")
    medical_expense_te = fields.Float("Gastos Médicos TE-60")
    medical_expense_t = fields.Float("Gastos Médicos TE-61-65")
    amount_rap = fields.Float("RAP")
    amount_ivm = fields.Float("Aportaciones Vejez y Muerte", compute="_compute_amount_ivm", store=False)
    isr_range_ids = fields.One2many("hr.isr.ranges", "parent_id", "Rangos")

    def _compute_amount_ivm(self):
        ihss = self.env['l10n.hn.ihss.settings'].search([('state', '=', 'validated')], limit=1)
        for rec in self:
            if ihss:
                rec.amount_ivm = round(ihss.ivm_ceiling_monthly * (ihss.ivm_employee_rate / 100.0), 2) * 12
            else:
                rec.amount_ivm = 0


class HrISRRanges(models.Model):
    _name = "hr.isr.ranges"
    _description = "ISR Ranges"

    parent_id = fields.Many2one("hr.isr", "ISR", ondelete='cascade')
    amount_from = fields.Float("Desde", required=True)
    amount_to = fields.Float("Hasta", required=True)
    rate = fields.Float("Tasa %", required=True)
