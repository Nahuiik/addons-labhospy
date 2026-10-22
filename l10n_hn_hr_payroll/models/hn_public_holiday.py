# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from datetime import datetime, time
import pytz

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.fields import Domain


class HnPublicHoliday(models.Model):
    _name = 'hn.public.holiday'
    _description = 'Día festivo Honduras (maestro)'
    _order = 'date desc'

    name = fields.Char(string='Nombre', required=True)
    date = fields.Date(string='Fecha', required=True, index=True)
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        ondelete='cascade',
        help='Vacío = aplica a todas las compañías.',
    )
    calendar_leave_ids = fields.One2many(
        'resource.calendar.leaves',
        'hn_public_holiday_id',
        string='Marcas en horarios',
        readonly=True,
    )

    @api.constrains('date', 'company_id')
    def _check_unique_date_company(self):
        for rec in self:
            domain = [('date', '=', rec.date), ('id', '!=', rec.id)]
            if rec.company_id:
                domain.append(('company_id', '=', rec.company_id.id))
            else:
                domain.append(('company_id', '=', False))
            if self.search(domain, limit=1):
                raise ValidationError(_('Ya existe un festivo para esta fecha en esta compañía.'))

    def _get_companies_to_sync(self):
        """Compañías para las que sincronizar (solo país HN si es festivo global por compañía)."""
        if self.company_id:
            return self.company_id
        # Odoo 19: res.company.country_id no es stored; no usar en search domain.
        return self.env['res.company'].search([]).filtered(
            lambda c: c.country_id and c.country_id.code == 'HN'
        )

    def _get_calendars_to_sync(self):
        """Calendarios únicos para los que crear resource.calendar.leaves."""
        companies = self._get_companies_to_sync()
        cal_ids = list({cid for cid in companies.mapped('resource_calendar_id').ids if cid})
        return self.env['resource.calendar'].browse(cal_ids)

    def _leave_vals_for_calendar(self, calendar):
        """Valores para crear resource.calendar.leaves en un calendario."""
        tz_name = calendar.tz if calendar else 'America/Tegucigalpa'
        tz = pytz.timezone(tz_name)
        date_from = tz.localize(datetime.combine(self.date, time.min))
        date_to = tz.localize(datetime.combine(self.date, time(23, 59, 59)))
        from_utc = date_from.astimezone(pytz.UTC).replace(tzinfo=None)
        to_utc = date_to.astimezone(pytz.UTC).replace(tzinfo=None)
        vals = {
            'name': self.name,
            'date_from': from_utc,
            'date_to': to_utc,
            'resource_id': False,
            'time_type': 'leave',
            'hn_public_holiday_id': self.id,
            'calendar_id': calendar.id if calendar else False,
        }
        if 'sv_public_holiday_id' in self.env['resource.calendar.leaves']._fields:
            vals['sv_public_holiday_id'] = False
        return vals

    def _sync_to_calendar_leaves(self):
        """Crea o actualiza resource.calendar.leaves a partir de este festivo."""
        RCL = self.env['resource.calendar.leaves'].sudo().with_context(
            l10n_skip_calendar_leave_reevaluate=True,
        )
        for rec in self:
            calendars = rec._get_calendars_to_sync()
            existing = RCL.search([('hn_public_holiday_id', '=', rec.id)])
            existing_by_calendar = {l.calendar_id.id if l.calendar_id else 0: l for l in existing}

            for calendar in calendars:
                cal_id = calendar.id if calendar else 0
                vals = rec._leave_vals_for_calendar(calendar)
                company = calendar.company_id or self.env.company
                if cal_id in existing_by_calendar:
                    existing_by_calendar[cal_id].with_company(company).write(vals)
                else:
                    # Incluir festivo global (sin calendar_id): hr_holidays prohíbe solape global+específico.
                    base_domain = [
                        ('resource_id', '=', False),
                        ('date_from', '<=', vals['date_to']),
                        ('date_to', '>=', vals['date_from']),
                        ('hn_public_holiday_id', '=', False),
                    ]
                    if 'sv_public_holiday_id' in RCL._fields:
                        base_domain.append(('sv_public_holiday_id', '=', False))
                    cal_or = (
                        Domain(['|', ('calendar_id', '=', False), ('calendar_id', '=', cal_id)])
                        if cal_id
                        else Domain([('calendar_id', '=', False)])
                    )
                    overlaps = RCL.search(
                        Domain.AND([
                            Domain(base_domain),
                            Domain(['|', ('company_id', '=', company.id), ('company_id', '=', False)]),
                            cal_or,
                        ])
                    )
                    if overlaps:
                        head, tail = overlaps[0], overlaps[1:]
                        if tail:
                            tail.unlink()
                        head.with_company(company).write(vals)
                    else:
                        RCL.with_company(company).create(vals)

            # Eliminar leaves de calendarios que ya no aplican
            valid_cal_ids = set(cal.id if cal else 0 for cal in calendars)
            to_unlink = existing.filtered(
                lambda l: (l.calendar_id.id if l.calendar_id else 0) not in valid_cal_ids
            )
            if to_unlink:
                to_unlink.unlink()

    def _remove_calendar_leaves(self):
        """Elimina los resource.calendar.leaves vinculados."""
        self.env['resource.calendar.leaves'].sudo().with_context(
            l10n_skip_calendar_leave_reevaluate=True,
        ).search([
            ('hn_public_holiday_id', 'in', self.ids),
        ]).unlink()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_to_calendar_leaves()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ('name', 'date', 'company_id')):
            self._sync_to_calendar_leaves()
        return res

    def unlink(self):
        self._remove_calendar_leaves()
        return super().unlink()
