# Notas de rendimiento (nómina HN/SV)

## Dónde perfilar

- Confirmación de `hr.payslip.run` y cálculo masivo de `hr.payslip` (`action_compute_sheet`).
- Wizards Excel en `gn_hr_payroll_employee_extras` (reportes con muchos empleados).

## Recomendaciones

- Evitar `search` / `browse` dentro del cuerpo de reglas salariales por línea de recibo; precargar catálogos por `(company_id, período)` cuando sea posible.
- Tras centralizar lógica quincenal en `payroll_biweekly_utils`, cualquier optimización de fechas debe hacerse **una sola vez** en ese módulo.

## Próximos pasos

- Medir con un lote real (N empleados) en entorno de prueba y anotar tiempos antes/después de cambios en reglas o informes.

