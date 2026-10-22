# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime, date


class GnPeriodLock(models.Model):
    _name = 'gn.period.lock'
    _description = 'Bloqueo de Período'
    _order = 'from_date desc, to_date desc'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo del bloqueo de período'
    )
    from_date = fields.Date(
        string='Fecha Desde',
        required=True,
        help='Fecha inicial del período bloqueado'
    )
    to_date = fields.Date(
        string='Fecha Hasta',
        required=True,
        help='Fecha final del período bloqueado'
    )
    journal_ids = fields.Many2many(
        comodel_name='account.journal',
        relation='gn_period_lock_journal_rel',
        column1='period_lock_id',
        column2='journal_id',
        string='Diarios',
        required=True,
        help='Diarios que serán bloqueados en este período'
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        help='Compañía a la que aplica este bloqueo'
    )
    state = fields.Selection(
        [
            ('locked', 'Bloqueado'),
            ('unlocked', 'Desbloqueado'),
        ],
        string='Estado',
        default='locked',
        required=True,
        help='Estado del bloqueo de período'
    )
    locked_by = fields.Many2one(
        comodel_name='res.users',
        string='Bloqueado por',
        readonly=True,
        help='Usuario que creó el bloqueo'
    )
    unlocked_by = fields.Many2one(
        comodel_name='res.users',
        string='Desbloqueado por',
        readonly=True,
        help='Usuario que desbloqueó el período'
    )
    unlock_date = fields.Datetime(
        string='Fecha de Desbloqueo',
        readonly=True,
        help='Fecha y hora en que se desbloqueó el período'
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
        help='Si está desactivado, el bloqueo no se aplicará'
    )
    is_currently_blocking = fields.Boolean(
        string="Blocking Today",
        compute="_compute_is_currently_blocking",
        help="True when the rule is locked, active, and today's date falls in the range.",
    )

    @api.depends("from_date", "to_date", "state", "active")
    def _compute_is_currently_blocking(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_currently_blocking = bool(
                rec.active
                and rec.state == "locked"
                and rec.from_date
                and rec.to_date
                and rec.from_date <= today <= rec.to_date
            )

    @api.constrains('from_date', 'to_date')
    def _check_dates(self):
        """Validar que la fecha desde sea menor o igual a la fecha hasta"""
        for record in self:
            if record.from_date and record.to_date:
                if record.from_date > record.to_date:
                    raise ValidationError(_(
                        'La fecha desde debe ser menor o igual a la fecha hasta.'
                    ))

    @api.constrains('from_date', 'to_date', 'journal_ids', 'company_id', 'active')
    def _check_overlapping_periods(self):
        """Validar que no existan períodos bloqueados superpuestos para los mismos diarios"""
        for record in self:
            if not record.active or record.state != 'locked':
                continue
            
            overlapping = self.search([
                ('id', '!=', record.id),
                ('active', '=', True),
                ('state', '=', 'locked'),
                ('company_id', '=', record.company_id.id),
                ('journal_ids', 'in', record.journal_ids.ids),
                '|', '|',
                '&', ('from_date', '<=', record.from_date), ('to_date', '>=', record.from_date),
                '&', ('from_date', '<=', record.to_date), ('to_date', '>=', record.to_date),
                '&', ('from_date', '>=', record.from_date), ('to_date', '<=', record.to_date),
            ])
            
            if overlapping:
                raise ValidationError(_(
                    'Ya existe un período bloqueado que se superpone con este período '
                    'para uno o más de los diarios seleccionados.'
                ))

    @api.model_create_multi
    def create(self, vals_list):
        """Asignar usuario que crea el bloqueo"""
        for vals in vals_list:
            if 'locked_by' not in vals:
                vals['locked_by'] = self.env.user.id
        return super().create(vals_list)

    def action_lock(self):
        """Acción para bloquear el período"""
        self.write({
            'state': 'locked',
            'locked_by': self.env.user.id,
            'unlocked_by': False,
            'unlock_date': False,
        })
        return True

    def action_unlock(self):
        """Acción para desbloquear el período"""
        if not self.env.user.has_group('gn_lock_date.group_period_lock_unlock'):
            raise ValidationError(_(
                'No tiene permisos para desbloquear períodos. '
                'Contacte al administrador para obtener permisos especiales.'
            ))
        
        self.write({
            'state': 'unlocked',
            'unlocked_by': self.env.user.id,
            'unlock_date': fields.Datetime.now(),
        })
        return True

    @api.model
    def check_period_lock(self, move_date, journal_id, company_id):
        """
        Verificar si una fecha y diario están bloqueados
        
        :param move_date: Fecha del movimiento contable
        :param journal_id: ID del diario
        :param company_id: ID de la compañía
        :return: True si está bloqueado, False si no
        """
        if not move_date or not journal_id or not company_id:
            return False
        
        locked_periods = self.search([
            ('active', '=', True),
            ('state', '=', 'locked'),
            ('company_id', '=', company_id),
            ('journal_ids', 'in', [journal_id]),
            ('from_date', '<=', move_date),
            ('to_date', '>=', move_date),
        ])
        
        return bool(locked_periods)

    @api.model
    def get_lock_message(self, move_date, journal_id, company_id):
        """
        Obtener mensaje de bloqueo para una fecha y diario
        
        :param move_date: Fecha del movimiento contable
        :param journal_id: ID del diario
        :param company_id: ID de la compañía
        :return: Mensaje de bloqueo o False
        """
        if not move_date or not journal_id or not company_id:
            return False
        
        locked_periods = self.search([
            ('active', '=', True),
            ('state', '=', 'locked'),
            ('company_id', '=', company_id),
            ('journal_ids', 'in', [journal_id]),
            ('from_date', '<=', move_date),
            ('to_date', '>=', move_date),
        ])
        
        if locked_periods:
            period = locked_periods[0]
            return _(
                'No puede crear/modificar/publicar movimientos contables para el diario "%(journal)s" '
                'en la fecha %(date)s porque el período desde %(from_date)s hasta %(to_date)s '
                'está bloqueado por "%(lock_name)s".',
                journal=self.env['account.journal'].browse(journal_id).display_name,
                date=move_date,
                from_date=period.from_date,
                to_date=period.to_date,
                lock_name=period.name,
            )
        return False

    @api.model
    def _get_dashboard_summary(self, company_id):
        """Summarize granular journal period locks for the Lock Dates dashboard."""
        today = fields.Date.context_today(self)
        domain_base = [
            ("company_id", "=", company_id),
            ("active", "=", True),
            ("state", "=", "locked"),
        ]
        total_locked = self.search_count(domain_base)
        blocking_today = self.search_count(
            domain_base
            + [
                ("from_date", "<=", today),
                ("to_date", ">=", today),
            ]
        )
        sample_recs = self.search(
            domain_base
            + [
                ("from_date", "<=", today),
                ("to_date", ">=", today),
            ],
            limit=5,
            order="from_date desc",
        )
        samples = [
            {
                "id": r.id,
                "name": r.name,
                "from_date": fields.Date.to_string(r.from_date),
                "to_date": fields.Date.to_string(r.to_date),
                "journal_count": len(r.journal_ids),
                "is_currently_blocking": r.is_currently_blocking,
            }
            for r in sample_recs
        ]
        return {
            "blocking_today_count": blocking_today,
            "locked_rules_count": total_locked,
            "samples": samples,
        }

