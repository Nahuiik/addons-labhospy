# -*- coding: utf-8 -*-

from odoo import fields, models, api

class retentionsType(models.Model):
    _name = 'gn_retentions.retentions.type'
    _description = 'Retention Types'

    name = fields.Char(string="Name")
    percentage = fields.Float(string="Percentage")