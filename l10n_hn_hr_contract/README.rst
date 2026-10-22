=====================
l10n HN HR Contract
=====================

Summary
-------

*Agrega la opcion de contrato a Odoo 19.*

Descripción
-----------

Este módulo traslada a Odoo 19 Community (con ``bi_hr_payroll``) las funcionalidades
clave del configurador de contratos de Odoo 18 Enterprise:

- **Beneficios parametrizables** por estructura salarial y compañía.
- **Campos salariales adicionales** (salario con vacaciones, costo anual/ mensual).
- **Cálculo automático** del sacrificio salarial por días adicionales de vacaciones.
- **Generación de inputs de nómina** desde los beneficios mensuales.
- **Asignaciones automáticas de vacaciones** al aprobar el contrato.

Configuración
-------------

1. Ajuste las plantillas de beneficios desde ``RRHH › Configuración › Beneficios de contrato``.
2. Defina los días laborales y el tipo de vacaciones automático en ``RRHH › Configuración › Settings``.
3. Abra un empleado y, en la pestaña **Contrato HN**, configure beneficios/días adicionales.

Compatibilidad
--------------

- Odoo 19 Community.
- ``bi_hr_payroll`` y ``bi_hr_payroll_account``.



