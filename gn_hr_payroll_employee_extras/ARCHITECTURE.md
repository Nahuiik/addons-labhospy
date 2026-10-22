# Arquitectura: gn_hr_payroll_employee_extras

## Rol

Hub de **funcionalidad compartida** entre localizaciones de nómina (**Honduras** y **El Salvador**) cuando el dominio no pertenece a:

- `gn_hr_payroll_salary_management` (aumentos, anticipos, historial salarial genérico)
- `gn_hr_payroll_licenses` (licencias / tipos de licencia)

## Contenido actual

- **Conceptos recurrentes** y wizards asociados (asignación, reporte Excel).
- **Documentos de entrada** (tipos y descarga).
- **Utilidades Python** sin modelos Odoo: `models/payroll_biweekly_utils.py` (calendario quincenal 1–15 / 16–fin de mes) consumidas por `l10n_hn_hr_payroll` y `l10n_sv_hr_payroll`.

## Dependencias

- `depends`: `hr_payroll`.
- Las localizaciones `l10n_hn_hr_payroll` y `l10n_sv_hr_payroll` **dependen de este módulo**; no deben depender entre sí.

## Convención para código nuevo compartido

1. Implementar en `gn_hr_payroll_employee_extras` (modelos abstractos `models.AbstractModel`, mixins, helpers puros).
2. En `l10n_*`, heredar o importar; evitar copiar lógica de fechas quincenales u otras reglas idénticas entre países.

## Multi-compañía HN + SV

Ver pruebas en `l10n_sv_hr_payroll/tests/test_multi_company_hn_sv.py` y matriz manual en `UPGRADE_AND_QA.md` (raíz de este módulo).

