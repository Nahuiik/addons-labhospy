# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, models, _
from odoo.exceptions import UserError

from .hn_liquidation_calculator import (
    LiquidationInputDTO,
    build_lines_for_scenario,
    compute_salary_bases,
    snapshot_dto,
    tenure_total_months,
)


class HnLiquidationEngine(models.AbstractModel):
    _name = 'hn.liquidation.engine'
    _description = 'Motor de liquidación laboral HN'

    def _get_history_window(self, liquidation):
        """Filas de historial salarial en los 6 meses naturos previos a end_date (inclusive mes de cese)."""
        end = liquidation.end_date
        if not end or not liquidation.employee_id:
            return self.env['l10n.hn.employee.monthly.salary.history'].browse()
        start = (date(end.year, end.month, 1) - relativedelta(months=5))
        rows = self.env['l10n.hn.employee.monthly.salary.history'].search([
            ('employee_id', '=', liquidation.employee_id.id),
            ('company_id', '=', liquidation.company_id.id),
        ])
        return rows.filtered(
            lambda r: date(r.year, r.month, 1) >= start
            and date(r.year, r.month, 1) <= date(end.year, end.month, 1)
        ).sorted(key=lambda r: (r.year, r.month))

    def _monthly_amounts_from_history(self, liquidation):
        hist = self._get_history_window(liquidation)
        wages = [float(r.amount_monthly_display or 0) for r in hist]
        comm = [float(r.amount_commission or 0) for r in hist]
        return wages, comm

    def _compute_continuous_years(self, liquidation):
        if liquidation.start_date and liquidation.end_date:
            d = relativedelta(liquidation.end_date, liquidation.start_date)
            return d.years + d.months / 12.0 + d.days / 360.0
        return 0.0

    def _build_input_dto(self, liquidation):
        wages, comm = self._monthly_amounts_from_history(liquidation)
        cash = float(liquidation.current_wage_monthly or 0.0)
        if not cash and liquidation.employee_id.current_version_id:
            cash = float(liquidation.employee_id.current_version_id.wage or 0)
        kind = float(liquidation.input_in_kind_monthly or 0.0)
        sbd, sod, spd, meta = compute_salary_bases(
            monthly_wages_last_six=wages,
            monthly_commissions_last_six=comm,
            monthly_cash_wage=cash,
            in_kind_monthly_capped=kind,
        )
        if liquidation.input_spd_manual_override:
            spd = float(liquidation.input_spd_manual_override)
        if liquidation.input_sod_manual_override:
            sod = float(liquidation.input_sod_manual_override)
        if liquidation.input_sbd_manual_override:
            sbd = float(liquidation.input_sbd_manual_override)

        months = tenure_total_months(
            liquidation.years_worked,
            liquidation.months_worked,
            liquidation.days_worked,
        )
        cyears = self._compute_continuous_years(liquidation)
        occ = float(liquidation.occupational_daily_wage or 0) or spd

        dto = LiquidationInputDTO(
            total_months=months,
            continuous_service_years=cyears,
            is_microenterprise=bool(liquidation.company_id.is_microenterprise),
            sbd=sbd,
            sod=sod,
            spd=spd,
            occupational_daily=occ,
            thirteenth_paid_in_cycle=float(liquidation.input_thirteenth_paid_cycle or 0),
            fourteenth_paid_in_cycle=float(liquidation.input_fourteenth_paid_cycle or 0),
            vacation_days_accrued_unpaid=float(liquidation.input_vacation_days_accrued or 0),
            vacation_proportional_days=float(liquidation.input_vacation_proportional_days or 0),
            pending_salary_days=float(liquidation.input_pending_salary_days or 0),
            pending_other_income=float(liquidation.input_other_pending_income or 0),
            employer_omitted_notice=bool(liquidation.employer_omitted_notice),
            employee_renounced_notice=bool(liquidation.employee_renounced_notice),
            force_proportional_vacation_company=bool(
                liquidation.force_proportional_vacation_company
            ),
        )
        return dto, meta

    def _thirteenth_fourteenth_lines(self, liquidation, sbd):
        vals_inc = []
        seq = 900
        end = liquidation.end_date
        emp = liquidation.employee_id
        paid13 = float(liquidation.input_thirteenth_paid_cycle or 0)
        paid14 = float(liquidation.input_fourteenth_paid_cycle or 0)

        Th = self.env['l10n.hn.thirteenth.month']
        Fo = self.env['l10n.hn.fourteenth.month']

        th = Th.search([
            ('employee_id', '=', emp.id),
            ('year', '=', end.year),
        ], limit=1)
        if not th:
            th = Th.create({'employee_id': emp.id, 'year': end.year})
        th_amount = float(th.calculated_amount or 0)
        rem13 = max(0.0, th_amount - paid13)
        if rem13 > 0:
            vals_inc.append({
                'sequence': seq,
                'concept': 'thirteenth_month',
                'name': _('Décimo tercer mes (ciclo %d, SBD)') % end.year,
                'amount': round(rem13, 2),
                'salary_base_used': 'sbd',
                'rule_origin': 'labor_rule',
                'legal_note': _('Monto desde registro 13°; descontar anticipos en cabecera. SBD=%.2f') % sbd,
            })
            seq += 1

        fo = Fo.search([
            ('employee_id', '=', emp.id),
            ('year', '=', end.year),
        ], limit=1)
        if not fo:
            fo = Fo.create({'employee_id': emp.id, 'year': end.year})
        fo_amount = float(fo.calculated_amount or 0)
        rem14 = max(0.0, fo_amount - paid14)
        if rem14 > 0:
            vals_inc.append({
                'sequence': seq,
                'concept': 'fourteenth_month',
                'name': _('Décimo cuarto mes (período jul–jun; SBD)'),
                'amount': round(rem14, 2),
                'salary_base_used': 'sbd',
                'rule_origin': 'labor_rule',
                'legal_note': _('Monto desde registro 14°; descontar anticipos en cabecera'),
            })
            seq += 1

        return vals_inc

    def apply_to_record(self, liquidation, *, simulation=False, log_reason=None):
        """Recalcula y escribe líneas."""
        self._check_company(liquidation)
        if liquidation.state in ('waiting_approval', 'approved', 'liquidated'):
            raise UserError(_('No puede recalcular en este estado. Cancele o cree un borrador nuevo.'))

        dto, meta = self._build_input_dto(liquidation)
        legal = liquidation.legal_termination_reason or liquidation._map_legacy_reason()

        enable_penalty = self.env['ir.config_parameter'].sudo().get_param(
            'l10n_hn_liquidation.enable_resignation_notice_penalty', 'False'
        ).lower() in ('1', 'true', 'yes')

        lines = build_lines_for_scenario(
            legal,
            dto,
            death_risk_classification=liquidation.death_risk_classification or 'non_occupational',
            employer_fault_vacation_proportional=liquidation.employer_fault_vacation_proportional,
            apply_literal_g_resignation=not liquidation.company_id.is_microenterprise,
            apply_literal_g_natural_death=not liquidation.company_id.is_microenterprise,
            habilitar_descuento_renuncia_sin_preaviso=enable_penalty,
        )

        liquidation.income_ids.with_context(hn_liquidation_engine_recompute=True).unlink()
        liquidation.deduction_ids.with_context(hn_liquidation_engine_recompute=True).unlink()

        income_concepts = {
            k for k, _ in self.env['l10n.hn.liquidation.income']._fields['concept'].selection
        }
        deduction_concepts = {
            k for k, _ in self.env['l10n.hn.liquidation.deduction']._fields['concept'].selection
        }

        for line in sorted([l for l in lines if l.side == 'income'], key=lambda x: x.sequence):
            concept = line.concept if line.concept in income_concepts else 'other'
            self.env['l10n.hn.liquidation.income'].create({
                'liquidation_id': liquidation.id,
                'sequence': line.sequence,
                'concept': concept,
                'concept_code': line.concept_code or line.concept,
                'name': line.name,
                'amount': line.amount,
                'salary_base_used': line.salary_base_used,
                'quantity_days': line.quantity_days,
                'quantity_hours': line.quantity_hours,
                'payee_type': line.payee_type,
                'legal_note': line.legal_note,
                'rule_origin': line.rule_origin,
            })

        for line in sorted([l for l in lines if l.side == 'deduction'], key=lambda x: x.sequence):
            concept = line.concept if line.concept in deduction_concepts else 'other'
            self.env['l10n.hn.liquidation.deduction'].create({
                'liquidation_id': liquidation.id,
                'sequence': line.sequence,
                'concept': concept,
                'concept_code': line.concept_code or line.concept,
                'name': line.name,
                'amount': line.amount,
                'salary_base_used': line.salary_base_used,
                'quantity_days': line.quantity_days,
                'legal_note': line.legal_note,
                'rule_origin': line.rule_origin,
            })

        for inc in self._thirteenth_fourteenth_lines(liquidation, dto.sbd):
            self.env['l10n.hn.liquidation.income'].create(dict(inc, liquidation_id=liquidation.id))

        liquidation._hn_engine_apply_loan_deductions()

        snap = snapshot_dto(lines, {
            'bases': {'sbd': dto.sbd, 'sod': dto.sod, 'spd': dto.spd},
            'meta': meta,
            'legal_reason': legal,
            'simulation': simulation,
        })
        vals_write = {
            'calculation_snapshot_json': snap,
            'sbd_computed': dto.sbd,
            'sod_computed': dto.sod,
            'spd_computed': dto.spd,
            'is_simulation': bool(simulation),
        }
        if simulation:
            vals_write['state'] = 'simulated'
        else:
            vals_write['state'] = 'draft'
        liquidation.write(vals_write)

        if log_reason:
            snap_store = snap if len(snap) <= 65000 else snap[:65000] + '...[truncado]'
            self.env['l10n.hn.liquidation.recompute.log'].create({
                'liquidation_id': liquidation.id,
                'reason': log_reason,
                'snapshot_json': snap_store,
            })

        liquidation.message_post(
            body=_('Liquidación recalculada. Bases: SBD=%.2f, SOD=%.2f, SPD=%.2f') % (dto.sbd, dto.sod, dto.spd)
        )
        return True

    def _check_company(self, liquidation):
        if not liquidation.employee_id or not liquidation.start_date or not liquidation.end_date:
            raise UserError(_('Complete empleado y fechas.'))
