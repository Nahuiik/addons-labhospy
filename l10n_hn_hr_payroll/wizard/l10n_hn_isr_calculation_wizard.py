# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import date
from dateutil.relativedelta import relativedelta
import calendar


class L10nHnIsrCalculationWizard(models.TransientModel):
    """Wizard to pre-calculate ISR for all employees for a given period"""
    _name = 'l10n.hn.isr.calculation.wizard'
    _description = 'ISR Pre-Calculation Wizard'

    config_id = fields.Many2one(
        'l10n.hn.isr.config',
        string='ISR Configuration',
        required=True,
        ondelete='cascade',
        help='ISR configuration to use for the calculation'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='config_id.company_id',
        readonly=True
    )
    period_type = fields.Selection([
        ('annual', 'Año completo'),
        ('monthly', 'Mes completo'),
        ('first_half', 'Primera quincena (1-15)'),
        ('second_half', 'Segunda quincena (16-fin)'),
    ], string='Tipo de Período', required=True, default='annual')
    year = fields.Integer(string='Año', required=True, default=lambda self: fields.Date.today().year)
    month = fields.Selection([
        ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'), ('4', 'Abril'),
        ('5', 'Mayo'), ('6', 'Junio'), ('7', 'Julio'), ('8', 'Agosto'),
        ('9', 'Septiembre'), ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre'),
    ], string='Mes', required=False, default=lambda self: str(fields.Date.today().month))
    employee_ids = fields.Many2many(
        'hr.employee',
        'l10n_hn_isr_calc_wiz_employee_rel',
        'wizard_id',
        'employee_id',
        string='Empleados',
        help='Dejar vacío para calcular para todos los empleados con contrato activo'
    )

    def _get_period_dates(self):
        """Get date_from and date_to based on period_type, year, month"""
        self.ensure_one()
        if self.period_type == 'annual':
            return None, None  # Handled separately
        month_int = int(self.month)
        last_day = calendar.monthrange(self.year, month_int)[1]
        if self.period_type == 'monthly':
            return date(self.year, month_int, 1), date(self.year, month_int, last_day)
        if self.period_type == 'first_half':
            return date(self.year, month_int, 1), date(self.year, month_int, 15)
        # second_half
        return date(self.year, month_int, 16), date(self.year, month_int, last_day)

    def _get_annual_periods(self):
        """Get all (date_from, date_to) tuples for the year based on config periodicity"""
        self.ensure_one()
        config = self.config_id
        periods = []
        if config.periodicity == 'monthly':
            for m in range(1, 13):
                last_day = calendar.monthrange(self.year, m)[1]
                periods.append((date(self.year, m, 1), date(self.year, m, last_day)))
        else:
            # biweekly - include only periods that apply per config.apply_in
            apply_in = config.apply_in or 'both'
            for m in range(1, 13):
                last_day = calendar.monthrange(self.year, m)[1]
                if apply_in in ('first_half', 'both'):
                    periods.append((date(self.year, m, 1), date(self.year, m, 15)))
                if apply_in in ('second_half', 'both'):
                    periods.append((date(self.year, m, 16), date(self.year, m, last_day)))
        return periods

    def _get_employees_to_calculate(self):
        """Get list of employees to calculate ISR for"""
        self.ensure_one()
        if self.employee_ids:
            return self.employee_ids
        domain = [
            ('company_id', '=', self.config_id.company_id.id),
            ('active', '=', True),
        ]
        employees = self.env['hr.employee'].search(domain)
        return employees.filtered(lambda e: e.sudo().current_version_id and not e.isr_excluded)

    def action_calculate(self):
        """Run ISR calculation for all selected employees"""
        self.ensure_one()
        if self.config_id.state != 'validated':
            raise UserError(_('La configuración ISR debe estar validada.'))
        if self.config_id.year != self.year:
            raise UserError(_(
                'La configuración ISR es para el año %(config_year)s. '
                'El período seleccionado es del año %(period_year)s.',
                config_year=self.config_id.year,
                period_year=self.year
            ))

        employees = self._get_employees_to_calculate()
        if not employees:
            raise UserError(_(
                'No hay empleados para calcular. '
                'Verifique que existan empleados con contrato activo y que no estén excluidos de ISR.'
            ))

        if self.period_type == 'annual':
            return self._action_calculate_annual(employees)
        return self._action_calculate_single_period(employees)

    def _action_calculate_annual(self, employees):
        """Calculate ISR for full year, all periods, simulating YTD accumulation"""
        self.ensure_one()
        config = self.config_id
        company = config.company_id
        cr = self.env.cr

        # Save original isr_retenido_ytd per version (version_id -> value)
        original_ytd = {}
        for emp in employees:
            v = emp.current_version_id.sudo() if emp.current_version_id else False
            if v:
                original_ytd[v.id] = v.isr_retenido_ytd or 0.0

        def _set_version_ytd(version_id, value):
            """Update isr_retenido_ytd via SQL to avoid ORM triggers"""
            if version_id:
                cr.execute(
                    "UPDATE hr_version SET isr_retenido_ytd = %s WHERE id = %s",
                    (float(value), version_id)
                )
                self.env['hr.version'].invalidate_recordset(
                    self.env['hr.version'].browse(version_id)
                )

        savepoint = cr.savepoint()
        errors = []
        try:
            # Remove existing audits for this config and year
            existing = self.env['l10n.hn.isr.audit'].search([
                ('config_id', '=', config.id),
                ('period_start', '>=', date(self.year, 1, 1)),
                ('period_end', '<=', date(self.year, 12, 31)),
            ])
            existing.unlink()

            periods = self._get_annual_periods()
            version_ytd = dict(original_ytd)

            for date_from, date_to in periods:
                for employee in employees:
                    try:
                        result = config.compute_withholding_for_period(
                            employee, date_from, date_to, company
                        )
                        audit_data = result.get('audit_data', {})
                        if audit_data and not audit_data.get('period_not_applicable'):
                            period_amt = audit_data.get('isr_period_amount', 0)
                            if period_amt and employee.current_version_id:
                                vid = employee.current_version_id.sudo().id
                                version_ytd[vid] = version_ytd.get(vid, 0) + period_amt
                                _set_version_ytd(vid, version_ytd[vid])
                    except Exception as e:
                        errors.append((employee.name, str(e)))
                        savepoint.rollback()
                        raise ValidationError(
                            _('Errores al calcular:\n%s') % '\n'.join(
                                f'• {name}: {err}' for name, err in errors
                            )
                        )

            # Restore original isr_retenido_ytd via SQL
            for vid, val in original_ytd.items():
                _set_version_ytd(vid, val)

        except ValidationError:
            raise
        except Exception:
            savepoint.rollback()
            raise

        return {
            'name': _('Auditoría ISR - %s') % self.year,
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.hn.isr.audit',
            'view_mode': 'list,form',
            'domain': [
                ('config_id', '=', config.id),
                ('period_start', '>=', date(self.year, 1, 1)),
                ('period_end', '<=', date(self.year, 12, 31)),
            ],
            'context': {'search_default_group_employee': 1},
        }

    def _action_calculate_single_period(self, employees):
        """Calculate ISR for a single period"""
        self.ensure_one()
        if not self.month:
            raise UserError(_('Seleccione el mes para calcular un período específico.'))
        date_from, date_to = self._get_period_dates()

        existing = self.env['l10n.hn.isr.audit'].search([
            ('config_id', '=', self.config_id.id),
            ('period_start', '=', date_from),
            ('period_end', '=', date_to),
        ])
        existing.unlink()

        errors = []
        for employee in employees:
            try:
                self.config_id.compute_withholding_for_period(
                    employee, date_from, date_to, self.config_id.company_id
                )
            except Exception as e:
                errors.append((employee.name, str(e)))

        if errors:
            raise ValidationError(
                _('Errores al calcular:\n%s') % '\n'.join(
                    f'• {name}: {err}' for name, err in errors
                )
            )

        return {
            'name': _('Auditoría ISR - %s') % date_from.strftime('%B %Y'),
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.hn.isr.audit',
            'view_mode': 'list,form',
            'domain': [
                ('period_start', '=', date_from),
                ('period_end', '=', date_to),
                ('config_id', '=', self.config_id.id),
            ],
            'context': {'search_default_group_employee': 1},
        }
