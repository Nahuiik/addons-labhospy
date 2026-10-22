# -*- coding: utf-8 -*-
"""
Script de diagnóstico para nómina: IHSS y RAP.
Ejecutar en shell de Odoo:
  odoo-bin shell -d GRUPOHMM
  >>> exec(open('addons/l10n_hn_hr_payroll/scripts/diagnostico_nomina_ihss_rap.py').read())

O usar con un payslip_id específico:
  >>> payslip_id = 1  # ID de la nómina a revisar
  >>> exec(open('addons/l10n_hn_hr_payroll/scripts/diagnostico_nomina_ihss_rap.py').read())
"""
from datetime import date

# Obtener última nómina o usar payslip_id si está definido
env = globals().get('env')
if not env:
    print("Ejecutar dentro del shell de Odoo")
    raise SystemExit(1)

payslip_id = globals().get('payslip_id')
if payslip_id:
    payslips = env['hr.payslip'].browse(payslip_id)
else:
    payslips = env['hr.payslip'].search([], order='id desc', limit=5)

if not payslips:
    print("No hay nóminas en el sistema")
    raise SystemExit(0)

for payslip in payslips:
    print("\n" + "=" * 60)
    print(f"NÓMINA: {payslip.name} | Empleado: {payslip.employee_id.name}")
    print(f"Período: {payslip.date_from} a {payslip.date_to}")
    print(f"Estructura: {payslip.struct_id.name} ({payslip.struct_id.code})")
    print("=" * 60)

    employee = payslip.employee_id
    version = employee.current_version_id

    # IHSS Settings
    year = payslip.date_to.year if payslip.date_to else date.today().year
    ihss = env['l10n.hn.ihss.settings'].search([
        ('year', '=', year),
        ('state', '=', 'validated'),
        ('company_id', '=', payslip.company_id.id)
    ], limit=1)

    if ihss:
        period_days = (payslip.date_to - payslip.date_from).days + 1 if payslip.date_from and payslip.date_to else 15
        ceiling_ivm = ihss.get_ceiling_for_period(period_days, 'ivm')
        ceiling_em = ihss.get_ceiling_for_period(period_days, 'em')
        base = sum(payslip.line_ids.filtered(lambda l: l.code == 'BASIC').mapped('total')) or (version.wage or 0) / (2.0 if period_days <= 16 else 1.0) if version else 0
        if payslip.struct_id.code in ('HN_BIWEEKLY', 'HN_MONTHLY'):
            base = next((l.total for l in payslip.line_ids if l.code == 'BASIC'), 0)
        taxable_ivm = min(base, ceiling_ivm)
        taxable_em = min(base, ceiling_em)
        calc_ivm = round(taxable_ivm * (ihss.ivm_employee_rate / 100.0), 2)
        calc_em = round(taxable_em * (ihss.em_employee_rate / 100.0), 2)
        calc_total = calc_ivm + calc_em

        print("\n--- IHSS Settings ---")
        print(f"  IVM techo mensual: {ihss.ivm_ceiling_monthly}")
        print(f"  EM techo mensual: {ihss.em_ceiling_monthly}")
        print(f"  Cuota IVM mensual (IHSS Settings): {ihss.ivm_quota_monthly}")
        print(f"  Cuota EM mensual (IHSS Settings): {ihss.em_quota_monthly}")
        print(f"  IHSS mensual total (Settings): {ihss.ihss_amount_monthly}")
        print(f"  Incluir en: {ihss.include_in} (1ra: {ihss.apply_first_quincena}, 2da: {ihss.apply_second_quincena})")
        print(f"\n  Para este período ({period_days} días):")
        print(f"  Techo IVM período: {ceiling_ivm}")
        print(f"  Techo EM período: {ceiling_em}")
        print(f"  Base salarial período: {base}")
        print(f"  Base gravable IVM (min(base,techo)): {taxable_ivm}")
        print(f"  Base gravable EM: {taxable_em}")
        print(f"  IHSS calculado (IVM+EM): {calc_total}")

        line_ihss = payslip.line_ids.filtered(lambda l: l.code in ('IHSS_EMP', 'IHSS_IVM_EMP', 'IHSS_EM_EMP'))
        if not line_ihss:
            line_ihss = payslip.line_ids.filtered(lambda l: 'IHSS' in (l.code or ''))
        recibo_ihss = abs(sum(line_ihss.mapped('total')))
        print(f"  IHSS en recibo: {recibo_ihss}")
        if abs(calc_total - recibo_ihss) > 0.02:
            print(f"  ⚠ DISCREPANCIA: diff = {recibo_ihss - calc_total}")
    else:
        print("\n--- IHSS: No hay configuración validada para este año/empresa")

    # RAP
    print("\n--- RAP ---")
    if version:
        print(f"  rap_excluded: {employee.rap_excluded}")
        print(f"  rap_setup_id: {version.rap_setup_id.name if version.rap_setup_id else 'No'}")
        print(f"  rap_fee (asignado): {version.rap_fee or 'No'}")
        print(f"  rap_manual: {version.rap_manual}")
        print(f"  rap_foviif_amount_monthly: {version.rap_foviif_amount_monthly}")
        print(f"  rap_foviif_amount_biweekly: {version.rap_foviif_amount_biweekly}")

    line_rap = payslip.line_ids.filtered(lambda l: l.code == 'RAP_FOVIIF_EMP')
    recibo_rap = abs(sum(line_rap.mapped('total')))
    print(f"  RAP en recibo: {recibo_rap}")
    if recibo_rap == 0 and version and not employee.rap_excluded and (version.rap_fee or version.rap_foviif_amount_biweekly or version.rap_foviif_amount_monthly):
        print("  ⚠ RAP debería aparecer pero está en 0. Recalcular nómina después de actualizar el módulo.")

    print()
