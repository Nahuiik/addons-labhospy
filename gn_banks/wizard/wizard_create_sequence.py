# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class WizardCreateSequence(models.TransientModel):
    _name = 'wizard.create.sequence'
    _description = 'Wizard para crear y editar secuencias bancarias'

    sequence_id = fields.Many2one('ir.sequence', string='Secuencia a editar', readonly=True)
    journal_id = fields.Many2one('account.journal', string='Diario', required=True, readonly=True)
    name = fields.Char(string='Nombre', required=True)
    prefix = fields.Char(string='Prefijo', required=True)
    suffix = fields.Char(string='Sufijo')
    padding = fields.Integer(string='Tamaño de secuencia', default=0, required=True)
    number_increment = fields.Integer(string='Paso', default=1, required=True)
    number_next = fields.Integer(string='Siguiente número', default=1, required=True)
    implementation = fields.Selection([
        ('standard', 'Estándar'),
        ('no_gap', 'No gap')
    ], string='Implementación', default='standard', required=True)
    move_type = fields.Selection([
        ('debit', 'Débitos'),
        ('credit', 'Créditos'),
        ('deposit', 'Depósitos'),
        ('check', 'Cheques'),
        ('transference', 'Transferencias'),
        ('transference_banks', 'Transferencias entre Bancos'),
        ('credit_card', 'Tarjeta de Crédito'),
        ('caja', 'Caja'),
        ('otro', 'Otro')
    ], string='Tipo de transacción', required=True)
    code = fields.Char(string='Código de secuencia')
    active = fields.Boolean(string='Activo', default=True)
    use_date_range = fields.Boolean(string='Usar subsecuencias por date_range', default=False)

    @api.model
    def default_get(self, fields_list):
        res = super(WizardCreateSequence, self).default_get(fields_list)
        if self.env.context.get('active_id') and self.env.context.get('active_model') == 'account.journal':
            journal = self.env['account.journal'].browse(self.env.context['active_id'])
            res['journal_id'] = journal.id
        elif self.env.context.get('active_id') and self.env.context.get('active_model') == 'ir.sequence':
            sequence = self.env['ir.sequence'].browse(self.env.context['active_id'])
            res['sequence_id'] = sequence.id
            res['journal_id'] = sequence.journal_id.id
            res['name'] = sequence.name
            res['prefix'] = sequence.prefix
            res['suffix'] = sequence.suffix or ''
            res['padding'] = sequence.padding
            res['number_increment'] = sequence.number_increment
            res['number_next'] = sequence.number_next
            res['implementation'] = sequence.implementation
            res['move_type'] = sequence.move_type
            res['code'] = sequence.code
            res['active'] = sequence.active
            res['use_date_range'] = sequence.use_date_range
        return res

    def _create_or_update_sequence(self):
        if self.sequence_id:
            existing = self.env['ir.sequence'].search([
                ('journal_id', '=', self.journal_id.id),
                ('move_type', '=', self.move_type),
                ('id', '!=', self.sequence_id.id)
            ])
            if existing:
                raise UserError(_('Ya existe otra secuencia configurada para el tipo de transacción "%s" en este diario.') % dict(self._fields['move_type'].selection)[self.move_type])

            sequence_vals = {
                'name': self.name,
                'code': self.code or f"bank.sequence.{self.journal_id.id}.{self.move_type}",
                'prefix': self.prefix,
                'suffix': self.suffix or '',
                'padding': self.padding,
                'number_increment': self.number_increment,
                'number_next': self.number_next,
                'implementation': self.implementation,
                'move_type': self.move_type,
                'active': self.active,
                'use_date_range': self.use_date_range,
            }
            self.sequence_id.write(sequence_vals)
            return self.sequence_id

        existing = self.env['ir.sequence'].search([
            ('journal_id', '=', self.journal_id.id),
            ('move_type', '=', self.move_type)
        ])
        if existing:
            raise UserError(_('Ya existe una secuencia configurada para el tipo de transacción "%s" en este diario.') % dict(self._fields['move_type'].selection)[self.move_type])

        sequence_vals = {
            'name': self.name,
            'code': self.code or f"bank.sequence.{self.journal_id.id}.{self.move_type}",
            'prefix': self.prefix,
            'suffix': self.suffix or '',
            'padding': self.padding,
            'number_increment': self.number_increment,
            'number_next': self.number_next,
            'implementation': self.implementation,
            'journal_id': self.journal_id.id,
            'move_type': self.move_type,
            'active': self.active,
            'use_date_range': self.use_date_range,
            'company_id': self.journal_id.company_id.id,
        }

        sequence = self.env['ir.sequence'].create(sequence_vals)
        return sequence

    def action_create_sequence(self):
        self.ensure_one()

        is_edit = bool(self.sequence_id)
        sequence = self._create_or_update_sequence()

        if is_edit:
            return {'type': 'ir.actions.act_window_close'}

        self.write({
            'name': '',
            'prefix': '',
            'suffix': '',
            'code': '',
            'move_type': False,
            'number_next': 1,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Secuencia creada'),
                'message': _('La secuencia "%s" ha sido creada exitosamente. Puede continuar agregando más secuencias.') % sequence.name,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_create_and_close(self):
        self.ensure_one()
        self._create_or_update_sequence()
        return {'type': 'ir.actions.act_window_close'}
