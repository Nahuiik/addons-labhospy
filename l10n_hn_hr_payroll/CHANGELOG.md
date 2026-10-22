# Changelog

## [19.0.1.0.42] - 2026-03-24

### Revertido / consolidado
- Eliminado el módulo intermedio **`gn_hr_driver_license`**: licencias de conducir de nuevo **solo en `l10n_hn_hr_payroll`** (modelos, vistas, datos HN, regla multicompañía).
- Migración `19.0.1.0.42/pre-migrate.py`: devuelve XML IDs desde `gn_hr_driver_license` a `l10n_hn_hr_payroll` **antes** de cargar datos (necesario para menús SV).
- `l10n_sv_hr_payroll` vuelve a depender de HN para el catálogo; SV añade datos propios en su módulo (`l10n_sv_driver_license_types_data.xml`).

## [19.0.1.0.41] - 2026-03-24

### Cambiado (obsoleto en .42)
- Intento con módulo `gn_hr_driver_license` — **revertido** en 19.0.1.0.42.

## [19.0.1.0.40] - 2026-03-24

### Añadido (Fase 0–1 plan HN/SV)
- **`countries`: `["hn"]`** en `__manifest__.py` (convención localización Odoo 19 / enterprise).
- **`country_id` = Honduras (`base.hn`)** en datos XML para `structure_biweekly`, `structure_monthly`,
  `structure_13th_month`, `structure_14th_month` (multi-país / filtrado por `hr.payroll.structure.country_id`).
- **Migración `19.0.1.0.40/post-migrate.py`**: asigna `country_id` HN a esas cuatro estructuras por XML ID
  (cubre BDs donde `noupdate` impidió refrescar el XML).

### XML IDs críticos (no renombrar; satélites y datos los referencian)
- `l10n_hn_hr_payroll.structure_biweekly`, `structure_monthly`, `structure_13th_month`, `structure_14th_month`
- Reglas y secuencias: ver plan técnico Anexo A (`localización_hn_en_payroll` en `.cursor/plans`).

## [19.0.1.0.9] - 2026-02-12

### Corregido
- **P0 - l10n_hn_isr_config.py**: Eliminados `hasattr()` en campos ORM que hacían
  inalcanzable el path legacy de cálculo ISR. Ahora se evalúa directamente el valor.
- **P1 - hr_payslip.py**: Eliminada mutación de `struct_id.input_line_type_ids` durante
  cómputo de nómina (`_sync_recurring_concepts`). Los tipos de input deben pre-configurarse.
- **P1 - hr_payslip.py**: `_update_isr_ytd` ahora usa la versión del período (`_get_version_for_period`)
  en vez de `current_version_id`, que podía ser de otro período.
- **P1 - hr_payslip.py**: Alineada frontera biweekly `<= 15` (antes `< 15` en `_schedule_timedelta`).
- **P1 - hr_payslip.py**: Eliminada limpieza destructiva `version.amount_other_income = 0` al confirmar
  nómina. La planilla ya gestiona el ciclo de vida de este campo.
- **P1 - hr_payslip.py**: Eliminados conceptos compartidos (`employee_id=False`) del dominio de
  búsqueda y su bloque de skip redundante en `_sync_recurring_concepts`.
- **P1 - l10n_hn_isr_config.py**: `_check_unique_validated` usa `search_count` con pre-filtro.
- **P1 - l10n_hn_isr_config.py**: `SimpleNamespace` mock reemplazado por `env['hr.payslip'].new()`.
- **P1 - l10n_hn_isr_config.py**: Parámetro redundante `config` eliminado de `_period_applies`.
- **P1 - l10n_hn_isr_config.py**: Bonus codes extraídos a constante `_BONUS_CODES`.
- **P1 - hr_employee.py**: `_compute_ihss_settings`, `_compute_rap_settings`, `_compute_isr_ytd`,
  `_compute_current_contract` refactorizados para búsqueda batch (N+1 → 1 query).
- **P1 - hr_employee.py**: `_compute_deduction_amounts` ISR: pre-fetch de payslips/líneas ISR batch.
- **P1 - hr_employee.py**: `_cron_trial_period_alert` envuelto en try/except para evitar que un
  fallo de correo detenga todo el proceso.
- **P1 - hr_employee.py**: `action_generate_required_documents` usa batch `create()`.
- **P2 - hr_version.py**: Extraído `_find_available_date_version()` helper, eliminando ~120 líneas
  de lógica duplicada entre `create()` y `write()` para resolución de conflictos de fecha.
- **P2 - hr_version.py**: Corregida precedencia de operador en `medical_default` (ternario vs `or`).
- **P2 - hr_version.py**: RAP rounding: `round(x * 12, 2)` en vez de `round(x, 2) * 12`.
- **P2 - hr_version.py**: `for...else` con `ValidationError` cuando las 30 fechas candidatas están ocupadas.
- **P2 - hr_version.py/hr_payslip.py**: Imports `timedelta`/`DEFAULT_SERVER_DATE_FORMAT` movidos al top.
- **P2 - hr_payslip.py**: `try/except AttributeError` → `if 'field' in _fields`.
- **P2 - hr_payslip.py**: `hasattr()` eliminados en `_schedule_timedelta`.
- **P2 - hr_employee.py**: `res_id=0` → `self[:1].id` en attachments Excel.
- **P2 - hr_employee.py**: `date.today()` → `fields.Date.context_today(self)`.
- **P2 - l10n_hn_isr_config.py**: Campos ORM redundantes eliminados de `l10n.hn.isr.audit`.
- **P2 - l10n_hn_isr_config.py**: Imports `relativedelta` inline eliminados (ya existe al top).
- **P2 - l10n_hn_isr_config.py**: Logger module-level `_logger` en vez de `import logging` inline.
- **P2 - family_relation_views.xml**: Typo "Conyuge" → "Cónyuge".

## [19.0.1.0.8] - 2026-02-12

### Corregido
- **P0 - hr_payslip.py**: Fusionados métodos `write()` y `compute_sheet()` que estaban definidos
  dos veces (la primera definición era código muerto). La sincronización de conceptos recurrentes
  y la re-sincronización post-cálculo ahora funcionan correctamente.
- **P0 - hr_payslip.py**: Eliminada recursión infinita potencial en `_sync_recurring_concepts`
  que llamaba `self.write()` sin protección, usando context flag `_skip_recurring_sync`.
- **P0 - l10n_hn_isr_config.py**: Corregido fallback de bracket ISR que aplicaba la tasa máxima
  (25%) cuando el ingreso gravable estaba por debajo del mínimo. Ahora retorna 0.0.
- **P0 - l10n_hn_isr_config.py**: Corregido doble conteo de deducciones ISR cuando una regla
  salarial estaba tanto en `deductible_rule_ids` como marcada con `isr_deductible=True`.
- **P0 - l10n_hn_isr_config.py**: Eliminado `ALTER TABLE` por SQL directo que se ejecutaba en
  cada cálculo de nómina (`_ensure_isr_audit_columns`). Los campos ya existen en el modelo ORM.
- **P0 - hr_version.py**: Corregida dependencia circular `@api.depends` entre `_compute_periodicity`
  y `_compute_schedule_pay` que causaba valores impredecibles de periodicidad.

### Mejorado
- **P0 - hr_employee.py**: Optimizado `_search_active_warnings_display` para procesar empleados
  en lotes de 200 con invalidación de cache, en lugar de cargar todos los empleados en memoria.
- **P1 - hr_employee_warning_type.py**: Implementado cache a nivel de request para
  `_is_warning_active()`, evitando N+1 queries en los 7+ métodos compute que lo invocan.
- **P1 - l10n_hn_isr_config.py**: Reemplazados loops N+1 en `_get_salary_ytd` y `_get_bonuses_ytd`
  con `read_group` de SQL directo (de ~240 queries a 2 por empleado).
- **P1 - l10n_hn_isr_config.py**: Bare `except:` reemplazado con `except (ValueError, TypeError, AttributeError)`.
- **P1 - l10n_hn_isr_config.py**: Creación de audit ISR envuelta en try/except con logging para
  no bloquear el cálculo de nómina si falla la auditoría.
- **hr_version.py**: Diccionarios de mapeo `_SCHEDULE_TO_PERIODICITY` y `_PERIODICITY_TO_SCHEDULE`
  definidos como constantes de clase para eliminar duplicación (antes definidos 6 veces).

## [19.0.1.0.7] - 2026-03-09

### Agregado
- Auto-inclusión en tabla "Establecer ISR" al crear/modificar contrato con salario.
- Sistema de alertas configurables para empleados (documentos, licencias, contratos, préstamos,
  período de prueba, padre/madre).
- Iconos de alertas en vista Kanban de empleados.
- Filtro de búsqueda "Con alertas activas" en vistas de empleados.
- Reportes Excel: referencias, estado de salud, alertas activas.
- Módulo `gn_hr_intercompany` para visibilidad inter-compañía de jerarquía de empleados.
