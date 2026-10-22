# Changelog - l10n_hn_hr_contract

## Versión 19.0.1.0.0

### ✅ Implementado

#### 1. Validaciones de Códigos de Input
- ✅ Validación de códigos de input en plantillas de beneficios
- ✅ Validación de códigos de input en líneas de beneficios contra estructuras salariales
- ✅ Verificación de existencia de códigos en reglas salariales

#### 2. Sistema Advantage Template Completo
- ✅ Métodos `get_attribute()` y `set_attribute_value()` en `hr.version`
- ✅ Integración con `hr.version.advantage.template` de bi_hr_payroll
- ✅ Soporte para códigos dinámicos de beneficios

#### 3. Mejoras de UI/UX
- ✅ Wizard para aplicar plantillas de beneficios a contratos
- ✅ Botón "Aplicar Plantilla de Beneficios" en vista de contrato
- ✅ Vista mejorada para gestión de beneficios

#### 4. Pruebas Funcionales
- ✅ Tests básicos para creación de plantillas
- ✅ Tests de validación de códigos
- ✅ Tests de cálculo de montos anuales

### 🔧 Correcciones
- ✅ Corregido método `_get_structure_type_id()` para retornar recordset correcto
- ✅ Mejorada validación de códigos de input en estructuras salariales
- ✅ Corregida carga de plantillas al cambiar estructura

### 📝 Archivos Nuevos
- `wizard/apply_benefit_template_wizard.py` - Wizard para aplicar plantillas
- `views/apply_benefit_template_wizard_views.xml` - Vistas del wizard
- `tests/test_contract_benefits.py` - Pruebas funcionales

### 🔄 Archivos Modificados
- `models/hr_version.py` - Agregados métodos Advantage Template
- `models/contract_benefit.py` - Agregadas validaciones de códigos
- `security/ir.model.access.csv` - Permisos del wizard
- `__manifest__.py` - Agregadas nuevas vistas

