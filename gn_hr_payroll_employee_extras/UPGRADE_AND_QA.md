# Upgrade y QA manual (HN + SV)

## Matriz multi-compañía (smoke)

| Paso | Compañía A (HN) | Compañía B (SV) |
|------|-----------------|-----------------|
| 1 | Crear `l10n.hn.payroll.period` para mes actual | Crear `l10n.sv.payroll.period` para mes actual |
| 2 | `hr.payslip.run` quincenal con `payroll_period_id` | `hr.payslip.run` quincenal con `l10n_sv_payroll_period_id` |
| 3 | Verificar que el lote HN no tiene SV período y viceversa (si ambos módulos instalados) | Mismo criterio |

Criterio de éxito: fechas del lote coinciden con el período; sin errores al guardar; grupos de usuario correctos según menú.

## Versiones

Al cambiar `payroll_biweekly_utils`, ejecutar tests de `gn_hr_payroll_employee_extras` y `-u` de `l10n_hn_hr_payroll` y `l10n_sv_hr_payroll`.

