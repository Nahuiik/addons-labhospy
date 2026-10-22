# -*- coding: utf-8 -*-

from odoo import api, fields, models

class City(models.Model):
    _inherit = 'res.city'
    
    district_code = fields.Char(string='Código de Distrito', size=4)

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    # Sobrescribimos el método para incluir el código de departamento en la dirección
    @api.onchange('city_id')
    def _onchange_city_id(self):
        res = super(ResPartner, self)._onchange_city_id()
        if self.city_id:
            self.city = self.city_id.name
            if self.city_id.district_code:
                self.zip = self.city_id.district_code
            if self.city_id.state_id:
                self.state_id = self.city_id.state_id
        return res