# Honduras Payroll Localization (l10n_hn_hr_payroll)

**Versión:** 19.0.1.0.8  
**Autor:** Grupo Nahuiik  
**Sitio web:** [www.gruponahuiik.com](https://www.gruponahuiik.com)  
**Contacto:** info@gruponahuiik.com  
**Licencia:** LGPL-3  

## Descripción

Módulo de localización de nómina hondureña para Odoo 19. Implementa el marco legal y fiscal
de Honduras para el cálculo de planillas, incluyendo IHSS, RAP, ISR, 13vo/14vo mes,
impuesto vecinal, liquidaciones laborales y más.

## Funcionalidades Principales

- **IHSS**: Configuración de techos IVM/EM, tasas obrero/patronal, cuotas mensuales/quincenales
- **RAP**: FOVIIF y FRL con techos, pisos y tasas configurables
- **ISR**: Algoritmo SAR 2026 con tabla progresiva, proyección anual, gastos médicos por edad,
  auditoría completa de retenciones
- **13vo y 14vo Mes**: Cálculo proporcional con cambios salariales durante el período
- **Planillas HE/TE/BD**: Horas extra, turnos extra y beneficios/deducciones por período
- **Impuesto Vecinal**: Brackets configurables, ingresos por empleado, historial de retención
- **Liquidación Laboral**: Cálculo de prestaciones, vacaciones, indemnización, preaviso
- **Conceptos Recurrentes**: Ingresos/deducciones automáticas en nómina (préstamos con cuotas)
- **Incapacidades IHSS**: Cálculo de días patrono vs IHSS según caso continuo
- **Alertas de Empleados**: Sistema configurable (documentos, licencias, contratos, período de prueba)
- **Reportes Excel**: Nómina, empleados, padres/hijos, referencias, salud, alertas activas, contratos
- **Auditoría de Nómina**: Checklist mensual/anual con asignación de actividades

## Dependencias

- `mail`
- `hr`
- `hr_payroll` (Enterprise)
- `hr_payroll_account` (Enterprise)
- `account`
- `hr_work_entry_holidays` (Enterprise)

### Dependencias Python

- `openpyxl` (generación de reportes Excel)

## Instalación

1. Copiar el módulo a la carpeta de addons
2. Instalar `openpyxl`: `pip install openpyxl`
3. Actualizar la lista de módulos en Odoo
4. Instalar "Honduras Payroll Localization"

## Estructura del Módulo

```
l10n_hn_hr_payroll/
├── models/          (48 modelos: nómina, empleados, ISR, IHSS, RAP, etc.)
├── wizard/          (15 wizards: importación, reportes, cálculos)
├── views/           (40 vistas XML: formularios, listas, kanban, menús)
├── data/            (24 archivos: reglas salariales, cron jobs, plantillas)
├── security/        (grupos, ACLs, record rules)
├── tests/           (11 archivos de pruebas automatizadas)
├── migrations/      (scripts de migración entre versiones)
├── report/          (plantillas de reportes QWeb)
├── scripts/         (utilidades de diagnóstico y mantenimiento)
└── static/          (manual de usuario HTML)
```

## Tests

```bash
python3 odoo-bin -d test_db --test-enable --test-tags l10n_hn_hr_payroll --stop-after-init
```

## Changelog

Ver [CHANGELOG.md](CHANGELOG.md) para el historial completo de cambios.
