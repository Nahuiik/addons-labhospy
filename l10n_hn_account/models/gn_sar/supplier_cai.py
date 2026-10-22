from odoo import models, fields, api
from odoo.exceptions import UserError, AccessError, ValidationError
import re

class InstallationAddress(models.Model):
    _name = 'supplier.cai'
    _description = 'Supplier CAI'

    contact_id = fields.Many2one('res.partner')
    supplier_cai_shot = fields.Char('CAI',required=True)
    supplier_prefix = fields.Char('Prefijo',required=True)
    supplier_cai_expires_shot = fields.Date("Fecha de Expiración",required=True)
    supplier_min_number_shot = fields.Char("Desde",required=True)
    supplier_max_number_shot = fields.Char("Hasta",required=True)
    active_supplier_cai = fields.Boolean('Activo')

    @api.constrains('supplier_cai_shot')
    def check_supplier_cai_shot(self):
        for rec in self:
            if rec.supplier_cai_shot:
                if not re.match("^(\\d|\\w){6}-(\\d|\\w){6}-(\\d|\\w){6}-(\\d|\\w){6}-(\\d|\\w){6}-(\\d|\\w){2}$",rec.supplier_cai_shot):
                    raise ValidationError('El CAI debe contener 37 caracteres alfanuméricos tomanto en cuenta los guiones e.g.: 000000-AAA111-222BBB-333333-CCC444-09 ')
        
            # res = self.env['supplier.cai'].search([('supplier_cai_shot','=',rec.supplier_cai_shot), ('id','!=',rec.id)])
            # if res:
            #     raise ValidationError('El CAI debe ser único para cada proveedor y no debe repetirse.')
            # else:
            #     pass

            ### Jonatan me dijo que el CAI puede repetirse por cada proveedor 04/02/25 (TICK-00318 Tlali)
            ### Liscy Viera


    @api.constrains('supplier_prefix')
    def check_supplier_prefix(self):
        for rec in self:
            if rec.supplier_prefix:
                if not re.match("^\\d{3}-\\d{3}-\\d{2}$",rec.supplier_prefix):
                    raise ValidationError('El prefijo debe contener 10 dígitos incluyendo los guiones e.g.: 000-000-00')

    @api.constrains('supplier_min_number_shot')
    def check_supplier_min_number_shot(self):
        for rec in self:
            if rec.supplier_min_number_shot:
                if not re.match("^\\d{8}$",rec.supplier_min_number_shot):
                    raise ValidationError(""" El número "desde" debe contener 8 dígitos """)

                if rec.supplier_max_number_shot:
                    print('='*100)
                    print(int(rec.supplier_max_number_shot))
                    print(int(rec.supplier_min_number_shot))
                    print('='*100)
                    if int(rec.supplier_min_number_shot)>int(rec.supplier_max_number_shot):
                        raise ValidationError(""" El número "desde" no puede ser mayor al número "hasta" """)

    @api.constrains('supplier_max_number_shot')
    def check_supplier_max_number_shot(self):
        for rec in self:
            if rec.supplier_max_number_shot:
                if not re.match("^\\d{8}$",rec.supplier_max_number_shot):
                    raise ValidationError(""" El número "hasta" debe contener 8 dígitos """)
                if rec.supplier_min_number_shot:
                    if int(rec.supplier_max_number_shot)<int(rec.supplier_min_number_shot):
                        raise ValidationError(""" El número "hasta" no puede ser menor al número "desde" """)