# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        index=True,
        help='Si está vacío, la estructura está disponible para todas las compañías del país.'
    )
    is_default = fields.Boolean(
        string='Por defecto',
        default=False,
        help='Estructura seleccionada por defecto en el wizard de generar nómina (una por compañía).'
    )

    @api.constrains('is_default', 'company_id')
    def _check_unique_default_per_company(self):
        for rec in self:
            if not rec.is_default:
                continue
            domain = [('is_default', '=', True), ('id', '!=', rec.id)]
            if rec.company_id:
                domain.append(('company_id', '=', rec.company_id.id))
            else:
                domain.append(('company_id', '=', False))
            if self.search(domain, limit=1):
                raise ValidationError(_(
                    'Solo puede haber una estructura por defecto por compañía. '
                    'Desmarque la actual antes de marcar otra.'
                ))

    def write(self, vals):
        if vals.get('is_default'):
            for rec in self:
                domain = [('is_default', '=', True), ('id', '!=', rec.id)]
                cid = vals.get('company_id', rec.company_id.id if rec.company_id else False)
                if cid:
                    domain.append(('company_id', '=', cid))
                else:
                    domain.append(('company_id', '=', False))
                self.search(domain).write({'is_default': False})
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_default'):
                cid = vals.get('company_id', False)
                domain = [('is_default', '=', True)]
                domain.append(('company_id', '=', cid))
                self.search(domain).write({'is_default': False})
        return super().create(vals_list)

    @api.model
    def cleanup_duplicate_rules(self):
        """Elimina reglas duplicadas de las estructuras quincenal y mensual"""
        structures = self.search([('code', 'in', ['HN_BIWEEKLY', 'HN_MONTHLY'])])
        
        for structure in structures:
            # Obtener nuestras reglas por XML ID
            try:
                if structure.code == 'HN_BIWEEKLY':
                    our_net_xmlid = 'l10n_hn_hr_payroll.salary_rule_net_biweekly'
                    our_basic_xmlid = 'l10n_hn_hr_payroll.salary_rule_basic_biweekly'
                    our_ihss_xmlid = 'l10n_hn_hr_payroll.salary_rule_ihss_employee_biweekly'
                    our_rap_xmlid = 'l10n_hn_hr_payroll.salary_rule_rap_foviif_employee_biweekly'
                    our_isr_xmlid = 'l10n_hn_hr_payroll.salary_rule_isr_retencion_biweekly'
                else:
                    our_net_xmlid = 'l10n_hn_hr_payroll.salary_rule_net_monthly'
                    our_basic_xmlid = 'l10n_hn_hr_payroll.salary_rule_basic_monthly'
                    our_ihss_xmlid = 'l10n_hn_hr_payroll.salary_rule_ihss_employee_monthly'
                    our_rap_xmlid = 'l10n_hn_hr_payroll.salary_rule_rap_foviif_employee_monthly'
                    our_isr_xmlid = 'l10n_hn_hr_payroll.salary_rule_isr_retencion_monthly'
                
                our_net_rule = self.env.ref(our_net_xmlid, raise_if_not_found=False)
                our_basic_rule = self.env.ref(our_basic_xmlid, raise_if_not_found=False)
                our_ihss_rule = self.env.ref(our_ihss_xmlid, raise_if_not_found=False)
                our_rap_rule = self.env.ref(our_rap_xmlid, raise_if_not_found=False)
                our_isr_rule = self.env.ref(our_isr_xmlid, raise_if_not_found=False)
                
                # Eliminar NET duplicados (dejar solo nuestra regla)
                if our_net_rule:
                    net_rules = self.env['hr.salary.rule'].search([
                        ('struct_id', '=', structure.id),
                        ('code', '=', 'NET'),
                        ('id', '!=', our_net_rule.id)
                    ])
                    net_rules.unlink()
                
                # Eliminar BASIC duplicados (dejar solo nuestra regla)
                if our_basic_rule:
                    basic_rules = self.env['hr.salary.rule'].search([
                        ('struct_id', '=', structure.id),
                        ('code', '=', 'BASIC'),
                        ('id', '!=', our_basic_rule.id)
                    ])
                    basic_rules.unlink()
                
                # Desactivar IHSS_IVM_EMP e IHSS_EM_EMP antiguas (ahora tenemos solo IHSS_EMP)
                # No las eliminamos porque pueden estar referenciadas en payslips históricos
                ihss_old_rules = self.env['hr.salary.rule'].search([
                    ('struct_id', '=', structure.id),
                    ('code', 'in', ['IHSS_IVM_EMP', 'IHSS_EM_EMP']),
                    ('active', '=', True)
                ])
                if our_ihss_rule:
                    # Excluir nuestra nueva regla IHSS_EMP si existe
                    ihss_old_rules = ihss_old_rules.filtered(lambda r: r.id != our_ihss_rule.id)
                ihss_old_rules.write({'active': False})
                
                # Desactivar IHSS_EMP duplicados (dejar solo nuestra regla activa)
                if our_ihss_rule:
                    ihss_rules = self.env['hr.salary.rule'].search([
                        ('struct_id', '=', structure.id),
                        ('code', '=', 'IHSS_EMP'),
                        ('id', '!=', our_ihss_rule.id),
                        ('active', '=', True)
                    ])
                    ihss_rules.write({'active': False})
                
                # Eliminar RAP_FOVIIF_EMP duplicados (dejar solo nuestra regla)
                if our_rap_rule:
                    rap_rules = self.env['hr.salary.rule'].search([
                        ('struct_id', '=', structure.id),
                        ('code', '=', 'RAP_FOVIIF_EMP'),
                        ('id', '!=', our_rap_rule.id)
                    ])
                    rap_rules.unlink()
                
                # Eliminar ISR duplicados (dejar solo nuestra regla)
                if our_isr_rule:
                    isr_rules = self.env['hr.salary.rule'].search([
                        ('struct_id', '=', structure.id),
                        ('code', '=', 'ISR'),
                        ('id', '!=', our_isr_rule.id)
                    ])
                    isr_rules.unlink()
                
                # Desactivar GROSS duplicados (dejar solo nuestra regla con categoría Bruto)
                # No se eliminan porque hr_payslip_line las referencia (payslips históricos)
                our_gross_xmlid = 'l10n_hn_hr_payroll.salary_rule_gross_biweekly' if structure.code == 'HN_BIWEEKLY' else 'l10n_hn_hr_payroll.salary_rule_gross_monthly'
                our_gross_rule = self.env.ref(our_gross_xmlid, raise_if_not_found=False)
                if our_gross_rule:
                    gross_rules = self.env['hr.salary.rule'].search([
                        ('struct_id', '=', structure.id),
                        ('code', '=', 'GROSS'),
                        ('id', '!=', our_gross_rule.id),
                        ('active', '=', True)
                    ])
                    gross_rules.write({'active': False})
            except Exception as e:
                # Fallback: eliminar por nombre si no se puede encontrar por XML ID
                net_rules = self.env['hr.salary.rule'].search([
                    ('struct_id', '=', structure.id),
                    ('code', '=', 'NET'),
                    ('name', '!=', 'Salario Neto')
                ])
                net_rules.unlink()
                
                basic_rules = self.env['hr.salary.rule'].search([
                    ('struct_id', '=', structure.id),
                    ('code', '=', 'BASIC'),
                    ('name', '!=', 'Salario Base')
                ])
                basic_rules.unlink()
            
            # Eliminar REIMBURSEMENT
            reimb_rules = self.env['hr.salary.rule'].search([
                ('struct_id', '=', structure.id),
                ('code', '=', 'REIMBURSEMENT')
            ])
            reimb_rules.unlink()
            
            # Eliminar 13TH_MONTH y 14TH_MONTH
            month_rules = self.env['hr.salary.rule'].search([
                ('struct_id', '=', structure.id),
                ('code', 'in', ['13TH_MONTH', '14TH_MONTH'])
            ])
            month_rules.unlink()
        
        return True
