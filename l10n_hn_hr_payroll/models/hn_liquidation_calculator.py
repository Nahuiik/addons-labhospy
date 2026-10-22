# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik
# Motor de liquidación — funciones puras (CT Honduras + reforma Dec. 150-2008).
# Referencia metodológica: https://www.trabajo.gob.hn/wp-content/uploads/2017/11/guiacalculo.pdf
# (topes de cesantía: Dec. 150-2008, no cifras obsoletas de la guía).

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any, List, Literal, Optional, Tuple

# Tipos de base salarial para trazabilidad en líneas
SalaryBaseType = Literal['none', 'sbd', 'sod', 'spd', 'occupational_daily']
RuleOriginType = Literal['labor_rule', 'company_policy']
PayeeType = Literal['employee', 'beneficiary']


@dataclass
class LiquidationLineDTO:
    """DTO de línea de ingreso/deducción antes de persistir en Odoo."""
    side: Literal['income', 'deduction']
    concept: str
    name: str
    amount: float
    sequence: int = 10
    salary_base_used: SalaryBaseType = 'none'
    quantity_days: float = 0.0
    quantity_hours: float = 0.0
    payee_type: PayeeType = 'employee'
    legal_note: str = ''
    rule_origin: RuleOriginType = 'labor_rule'
    concept_code: str = ''


@dataclass
class LiquidationInputDTO:
    """Entradas numéricas del motor (empaquetadas por el engine desde el registro Odoo)."""
    total_months: float
    continuous_service_years: float
    is_microenterprise: bool
    sbd: float  # salario base diario (13°/14°)
    sod: float  # salario ordinario diario (vacaciones)
    spd: float  # salario promedio diario (preaviso, cesantía)
    occupational_daily: float  # salario al momento del riesgo (muerte ocupacional)
    # Cesantía teórica completa (para literal g) — misma tabla Art. 120
    thirteenth_paid_in_cycle: float = 0.0
    fourteenth_paid_in_cycle: float = 0.0
    vacation_days_accrued_unpaid: float = 0.0
    vacation_proportional_days: float = 0.0
    pending_salary_days: float = 0.0
    pending_other_income: float = 0.0
    employer_omitted_notice: bool = True
    employee_renounced_notice: bool = False
    force_proportional_vacation_company: bool = False


def round_money(value: float, decimals: int = 2) -> float:
    return round(value + 1e-9, decimals)


def tenure_total_months(years: int, months: int, days: int) -> float:
    """Antigüedad en meses (aprox. 30 días/mes) desde relativedelta."""
    return years * 12 + months + (days / 30.0)


def notice_payment_days_art116(total_months: float) -> Tuple[float, str]:
    """Art. 116 CT — días de salario equivalentes al preaviso (mes 30 días).
    24 h = 1 día; 1 semana = 7; 2 semanas = 14; 1 mes = 30; 2 meses = 60.
    """
    if total_months < 3:
        return 1.0, 'Art. 116: menos de 3 meses (24 horas → 1 día de salario)'
    if total_months < 6:
        return 7.0, 'Art. 116: 3 a 6 meses (1 semana)'
    if total_months < 12:
        return 14.0, 'Art. 116: 6 meses a 1 año (2 semanas)'
    if total_months < 24:
        return 30.0, 'Art. 116: 1 a 2 años (1 mes)'
    return 60.0, 'Art. 116: más de 2 años (2 meses)'


def severance_salary_days_art120(total_months: float) -> float:
    """Días de salario por cesantía (tramos Art. 120), sin tope."""
    if total_months < 3:
        return 0.0
    if total_months < 6:
        return 10.0
    if total_months < 12:
        return 20.0
    years_float = total_months / 12.0
    return 30.0 * years_float


def severance_cap_months(is_microenterprise: bool) -> int:
    return 15 if is_microenterprise else 25


def severance_salary_days_capped(total_months: float, is_microenterprise: bool) -> float:
    """Cesantía con tope Dec. 150-2008 (25 o 15 meses × 30 días)."""
    raw = severance_salary_days_art120(total_months)
    cap_days = severance_cap_months(is_microenterprise) * 30.0
    return min(raw, cap_days)


# Tabla vacaciones Arts. 345-346 — días tras completar el año ordinal
def vacation_days_for_completed_year(year_index: int) -> int:
    if year_index <= 0:
        return 0
    if year_index == 1:
        return 10
    if year_index == 2:
        return 12
    if year_index == 3:
        return 15
    return 20


def vacation_proportional_divisor_for_year(year_index: int) -> int:
    """Criterio operativo guía STSS (36/30/24/18)."""
    if year_index == 1:
        return 36
    if year_index == 2:
        return 30
    if year_index == 3:
        return 24
    return 18


def build_lines_for_scenario(
    legal_reason: str,
    inp: LiquidationInputDTO,
    *,
    death_risk_classification: str = 'non_occupational',
    employer_fault_vacation_proportional: bool = False,
    apply_literal_g_resignation: bool = True,
    apply_literal_g_natural_death: bool = True,
    habilitar_descuento_renuncia_sin_preaviso: bool = False,
) -> List[LiquidationLineDTO]:
    """Genera líneas de ingreso/deducción según escenario legal."""
    lines: List[LiquidationLineDTO] = []
    seq = 10

    def add_income(
        concept: str,
        name: str,
        amount: float,
        *,
        base: SalaryBaseType = 'none',
        days: float = 0.0,
        hours: float = 0.0,
        payee: PayeeType = 'employee',
        note: str = '',
        origin: RuleOriginType = 'labor_rule',
    ):
        nonlocal seq
        lines.append(LiquidationLineDTO(
            side='income',
            concept=concept,
            concept_code=concept,
            name=name,
            amount=round_money(max(0.0, amount)),
            sequence=seq,
            salary_base_used=base,
            quantity_days=days,
            quantity_hours=hours,
            payee_type=payee,
            legal_note=note,
            rule_origin=origin,
        ))
        seq += 1

    def add_deduction(
        concept: str,
        name: str,
        amount: float,
        *,
        note: str = '',
        origin: RuleOriginType = 'company_policy',
    ):
        nonlocal seq
        lines.append(LiquidationLineDTO(
            side='deduction',
            concept=concept,
            concept_code=concept,
            name=name,
            amount=round_money(max(0.0, amount)),
            sequence=seq,
            legal_note=note,
            rule_origin=origin,
        ))
        seq += 1

    micro = inp.is_microenterprise
    months = inp.total_months
    spd, sod, sbd = inp.spd, inp.sod, inp.sbd

    # --- Derechos adquiridos (siempre que aplique monto) ---
    if inp.pending_salary_days > 0:
        add_income(
            'pending_days',
            'Salario pendiente por días laborados',
            inp.pending_salary_days * sod,
            base='sod',
            days=inp.pending_salary_days,
            note='Art. salario; base SOD',
        )
    if inp.vacation_days_accrued_unpaid > 0:
        add_income(
            'accrued_vacation',
            'Vacaciones causadas no gozadas (dinero)',
            inp.vacation_days_accrued_unpaid * sod,
            base='sod',
            days=inp.vacation_days_accrued_unpaid,
            note='Art. 349',
        )
    if inp.vacation_proportional_days > 0:
        if employer_fault_vacation_proportional:
            add_income(
                'proportional_vacation',
                'Vacaciones proporcionales (causa imputable al patrono)',
                inp.vacation_proportional_days * sod,
                base='sod',
                days=inp.vacation_proportional_days,
                note='Art. 349',
            )
        elif inp.force_proportional_vacation_company:
            add_income(
                'proportional_vacation',
                'Vacaciones proporcionales (política empresa — validar legalmente)',
                inp.vacation_proportional_days * sod,
                base='sod',
                days=inp.vacation_proportional_days,
                note='company_policy: Art. 350 orden público; no exceder acumulación ilegal',
                origin='company_policy',
            )
    if inp.pending_other_income > 0:
        add_income(
            'other',
            'Otros pagos pendientes',
            inp.pending_other_income,
            note='company_policy',
            origin='company_policy',
        )

    # --- Preaviso Art. 116 (pago patronal si omisión; no en renuncia ni muerte ni justificado)
    notice_days, notice_note = notice_payment_days_art116(months)

    if legal_reason == 'dismissal_unjustified' and inp.employer_omitted_notice and notice_days > 0:
        add_income(
            'advance_notice',
            'Preaviso (pago por omisión patronal)',
            notice_days * spd,
            base='spd',
            days=notice_days,
            note=notice_note,
        )

    # Renuncia: posible descuento sin preaviso — solo política
    if legal_reason == 'resignation' and inp.employee_renounced_notice and habilitar_descuento_renuncia_sin_preaviso:
        add_deduction(
            'other',
            'Responsabilidad trabajador por falta de preaviso (política empresa)',
            notice_days * spd * 0.5,
            note='NO automático por defecto; validar legalmente',
        )

    # --- Cesantía base (SPD) ---
    cesantia_full = severance_salary_days_capped(months, micro)

    def cesantia_payable_unjustified() -> float:
        if months < 3:
            return 0.0
        return cesantia_full * spd

    if legal_reason == 'dismissal_unjustified' and cesantia_full > 0:
        cap_m = severance_cap_months(micro)
        add_income(
            'severance',
            'Auxilio de cesantía (Art. 120; tope %d meses Dec. 150-2008)' % cap_m,
            cesantia_payable_unjustified(),
            base='spd',
            days=cesantia_full,
            note='Microempresa: 15 meses y sin literal g (Art. 120-A)' if micro else 'Tope general 25 meses',
        )

    # Renuncia ≥15 años: 35% literal g) — no micro
    if (
        legal_reason == 'resignation'
        and apply_literal_g_resignation
        and not micro
        and inp.continuous_service_years >= 15.0
        and months >= 3
    ):
        theoretical_days = severance_salary_days_capped(months, False)
        amount = theoretical_days * spd * 0.35
        add_income(
            'severance',
            'Literal g) Art. 120 — 35% cesantía teórica (renuncia ≥15 años)',
            amount,
            base='spd',
            days=theoretical_days * 0.35,
            note='Dec. 150-2008 literal g; no aplica micro Art. 120-A',
        )

    # Muerte natural >6m: 75% a beneficiarios — no micro
    if (
        legal_reason == 'death_natural'
        and apply_literal_g_natural_death
        and not micro
        and months >= 6
        and months >= 3
    ):
        theoretical_days = severance_salary_days_capped(months, False)
        amount = theoretical_days * spd * 0.75
        add_income(
            'severance',
            'Literal g) Art. 120 — 75% cesantía teórica (muerte natural >6m, beneficiarios)',
            amount,
            base='spd',
            days=theoretical_days * 0.75,
            payee='beneficiary',
            note='Dec. 150-2008 literal g; no aplica micro Art. 120-A',
        )

    # Muerte ocupacional Arts. 417-422
    if legal_reason == 'death_occupational':
        od = inp.occupational_daily or spd
        add_income(
            'occupational_funeral',
            'Indemnización: un mes de salario (gastos fúnebres)',
            30.0 * od,
            base='occupational_daily',
            days=30.0,
            payee='beneficiary',
            note='Arts. 417-422 CT',
        )
        add_income(
            'occupational_620',
            'Indemnización: 620 días de salario (riesgo profesional)',
            620.0 * od,
            base='occupational_daily',
            days=620.0,
            payee='beneficiary',
            note='No compensar automáticamente con IHSS; validar asesoría',
        )

    # Art. 120 f) — línea informativa si hay cobertura (el engine marcará flags)
    # No generamos monto automático aquí

    return lines


def compute_salary_bases(
    *,
    monthly_wages_last_six: List[float],
    monthly_commissions_last_six: List[float],
    monthly_cash_wage: float,
    in_kind_monthly_capped: float,
    work_hours_per_day: float = 8.0,
) -> Tuple[float, float, float, dict]:
    """Calcula SBD, SOD, SPD y metadatos.
    SBD: promedio mensual devengado últimos 6 meses / 30.
    SOD: salario ordinario diario (cash + especie hasta tope) + prorrateo 13+14 (2/12 del mensual).
    SPD: SOD + promedio diario de variables (comisiones u otras en la lista).
    """
    meta: dict = {'guide_note': 'SBD/SOD laborales Art. 361, 366, 368; guía STSS solo metodológica'}
    if monthly_wages_last_six:
        avg_m = sum(monthly_wages_last_six) / len(monthly_wages_last_six)
    else:
        avg_m = monthly_cash_wage
    sbd = avg_m / 30.0 if avg_m else monthly_cash_wage / 30.0
    cash_m = monthly_cash_wage or avg_m
    kind = min(in_kind_monthly_capped, 0.30 * cash_m) if cash_m else in_kind_monthly_capped
    sod_month_equiv = cash_m + kind + (2.0 / 12.0) * cash_m
    sod = sod_month_equiv / 30.0
    var_month = 0.0
    if monthly_commissions_last_six:
        var_month = sum(monthly_commissions_last_six) / len(monthly_commissions_last_six)
    spd = sod + (var_month / 30.0 if var_month else 0.0)
    return round_money(sbd), round_money(sod), round_money(spd), meta


def snapshot_dto(lines: List[LiquidationLineDTO], extra: Optional[dict] = None) -> str:
    payload = {
        'lines': [asdict(l) for l in lines],
        'extra': extra or {},
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)

