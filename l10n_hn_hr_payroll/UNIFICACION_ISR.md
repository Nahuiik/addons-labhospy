# Unificación de ISR: Tablas ISR → ISR Configuration

## Resumen

Se ha unificado el sistema de cálculo de ISR eliminando la duplicación entre `l10n.hn.isr.table` (Tablas ISR) y `l10n.hn.isr.config` (ISR Configuration), usando únicamente **ISR Configuration** como sistema completo.

## Diferencias entre los Modelos

### l10n.hn.isr.table (Tablas ISR) - DEPRECADO
- **Propósito**: Modelo simple/legacy para escalas de impuestos básicas
- **Características**:
  - Solo escalas de impuestos (`line_ids`)
  - Cálculo básico (`calculate_isr()`)
  - Campos: `exempt_amount`, `medical_services_deduction`
  - Sin configuración de deducciones
  - Sin proyecciones YTD
  - Sin auditoría integrada

### l10n.hn.isr.config (ISR Configuration) - ACTUAL
- **Propósito**: Sistema completo de retención a la fuente de ISR
- **Características**:
  - Escalas de impuestos (`bracket_ids`)
  - Cálculo completo con retención (`compute_withholding()`)
  - Configuración de deducciones (reglas salariales, tipos de entrada)
  - Gastos médicos por edad
  - Proyecciones YTD y anuales
  - Auditoría integrada (`l10n.hn.isr.audit`)
  - Manejo de 13vo y 14to mes
  - Deducciones de empleados (`l10n.hn.isr.employee_deduction`)

## Cambios Realizados

### 1. Datos Iniciales
- ✅ Creado `data/l10n_hn_isr_config_data.xml` con configuración ISR 2026
- ✅ Migrados datos de escalas desde `l10n.hn.isr.table` a `l10n.hn.isr.config`

### 2. Reglas Salariales
- ✅ Actualizada regla ISR en `l10n_hn_salary_rules_data.xml` para usar `l10n.hn.isr.config`
- ✅ La nueva implementación usa `compute_withholding()` que maneja automáticamente:
  - Ingresos YTD (básicos, variables, 13vo, 14to mes)
  - Deducciones YTD (de nómina, declaradas, gastos médicos)
  - Proyecciones anuales
  - Cálculo de retención del período

### 3. Menús
- ✅ Ocultado menú "ISR Tables" (deprecado)
- ✅ Mantenido solo "ISR Configuration" como sistema principal

### 4. Manifest
- ✅ Agregado `data/l10n_hn_isr_config_data.xml` al manifest

## Migración de Datos

Si tienes datos existentes en `l10n.hn.isr.table`, puedes migrarlos ejecutando:

```python
# Script de migración (ejecutar en shell de Odoo)
old_tables = env['l10n.hn.isr.table'].search([('state', '=', 'validated')])
for table in old_tables:
    # Crear configuración ISR
    config = env['l10n.hn.isr.config'].create({
        'year': table.year,
        'company_id': table.company_id.id,
        'periodicity': 'biweekly' if table.periodicity == 'biweekly' else 'monthly',
        'salario_minimo_promedio': table.exempt_amount / 10.0,  # Aproximación
        'medical_expenses_enabled': True,
        'medical_expenses_default_limit': table.medical_services_deduction * 12,  # Convertir a anual
        'state': 'validated',
    })
    
    # Migrar escalas
    for line in table.line_ids.sorted('min_amount'):
        env['l10n.hn.isr.config.bracket'].create({
            'config_id': config.id,
            'sequence': line.id,  # Usar ID como secuencia temporal
            'from_amount': line.min_amount,
            'to_amount': line.max_amount if line.max_amount > 0 else 0.0,
            'rate': line.rate,
            'fixed_quota': line.base_tax,
            'excess_over': line.min_amount,
        })
```

## Estado del Modelo Legacy

- ⚠️ `l10n.hn.isr.table` está **DEPRECADO** pero se mantiene por compatibilidad
- ✅ Se recomienda usar solo `l10n.hn.isr.config` para nuevas configuraciones
- ✅ Las reglas salariales principales ya usan `l10n.hn.isr.config`
- ✅ El menú de "ISR Tables" está oculto

## Beneficios de la Unificación

1. **Sistema Único**: Un solo modelo para toda la configuración ISR
2. **Funcionalidad Completa**: Retención a la fuente con YTD, proyecciones, auditoría
3. **Mantenimiento Simplificado**: Menos código duplicado
4. **Mejor Trazabilidad**: Auditoría integrada de todos los cálculos
5. **Flexibilidad**: Configuración de deducciones, gastos médicos por edad, etc.

## Próximos Pasos (Opcional)

Si deseas eliminar completamente `l10n.hn.isr.table`:

1. Verificar que no haya datos críticos en `l10n.hn.isr.table`
2. Migrar cualquier dato restante a `l10n.hn.isr.config`
3. Eliminar referencias en código
4. Eliminar modelo y vistas de `l10n.hn.isr.table`
5. Actualizar seguridad (ir.model.access.csv)

**Nota**: Por ahora se mantiene el modelo legacy por compatibilidad, pero está marcado como deprecado.
