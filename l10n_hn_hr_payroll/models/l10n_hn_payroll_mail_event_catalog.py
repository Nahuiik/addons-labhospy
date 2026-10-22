# -*- coding: utf-8 -*-
"""Catálogo de solo lectura: eventos que disparan correo en addons de Grupohmm."""
from odoo import fields, models


class L10nHnPayrollMailEventCatalog(models.Model):
    _name = 'l10n.hn.payroll.mail.event.catalog'
    _description = 'Catálogo de eventos de correo (referencia)'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    module = fields.Char(string='Módulo', required=True)
    name = fields.Char(string='Evento', required=True)
    trigger_description = fields.Text(string='Cuándo se envía')
    template_xml_id = fields.Char(
        string='Plantilla (xmlid)',
        help='XML ID de mail.template cuando aplica; vacío o texto si es notificación sin plantilla.',
    )
