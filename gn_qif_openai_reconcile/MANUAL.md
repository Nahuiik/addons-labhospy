# Manual de usuario — Importar estados de cuenta con IA (`gn_qif_openai_reconcile`)

Este documento describe cómo configurar y usar el módulo **Análisis Estados de Cuenta con OpenAI** en Odoo 19 (Community).

---

## 1. Qué hace el módulo

- **Importa** movimientos desde archivos **QIF** o **XLS** en el formato usado por **FICOHSA** (layout fijo en la primera hoja).
- Asocia el archivo a un **diario bancario** en Odoo y crea líneas de extracto con un identificador único por movimiento para **evitar duplicados** al reimportar.
- Opcionalmente usa **OpenAI** para:
  - enriquecer metadatos del extracto;
  - analizar movimientos frente a líneas ya existentes en Odoo y **sugerir modelos de conciliación** adaptados a tu operación.
- Registra **historial de importaciones** y gestiona **sugerencias** y **conocimiento por diario** para mejorar el análisis con el tiempo.

**Permisos:** usuarios con rol de contabilidad (facturación / usuario contable / administrador de contabilidad) según los modelos expuestos.

---

## 2. Requisitos previos

1. Módulo instalado: **Análisis Estados de Cuenta con OpenAI** (`gn_qif_openai_reconcile`).
2. En el servidor Odoo deben estar instalados los paquetes Python **`openai`** y **`xlrd`**.
3. Para usar la IA: una **API key** válida de OpenAI y, si aplica, cuota/créditos en tu cuenta.

---

## 3. Configuración global (OpenAI)

1. Vaya a **Contabilidad → Configuración → Ajustes** (aplicación **Contabilidad** en Ajustes generales, no el menú antiguo si ya usa el shell de ajustes por aplicación).
2. Dentro de la ficha o aplicación de **Contabilidad**, baje hasta el bloque **QIF OpenAI**.
3. Rellene:
   - **API Key de OpenAI** — clave secreta; trátela como contraseña.
   - **Modelo de IA** — p. ej. `gpt-4.1-mini` o el que indique su administrador.
4. Guarde.

> **Privacidad:** el envío a OpenAI implica que fragmentos de datos del extracto (descripciones, importes, fechas, etc.) salen de su instancia hacia el proveedor. Asegure cumplimiento interno (políticas de datos, DPA) antes de activar el análisis con IA en producción.

---

## 4. Configuración del diario bancario

1. Vaya a **Contabilidad → Configuración → Diarios** y abra el diario de **banco** que corresponde a la cuenta a importar.
2. En el tipo de sincronización / origen de extractos, elija la opción que permite **importar desde archivo (manual o QIF)**, de modo que aparezcan los campos de formato QIF.
3. Ajuste:
   - **QIF: separador decimal** — según cómo vengan los números en el archivo (p. ej. `.` o coherente con su exportación bancaria).
   - **QIF: formato de fechas** — `dd/mm/aa` o `mm/dd/aa` según el banco.
4. Guarde el diario.

Use siempre el diario correcto al importar, para que moneda, cuenta bancaria y `unique_import_id` queden alineados.

---

## 5. Abrir el asistente “Importar EC con IA”

- Menú: **Contabilidad → Transacciones → Importar EC con IA**  
  (también puede localizarlo por el nombre de la acción *Importar EC con IA*).

Se abre un asistente en ventana. Ahí se elige el **archivo**, el **diario de destino** y se lanzan las acciones del flujo.

---

## 6. Flujo de trabajo en el asistente

### 6.1. Archivo y diario

- **Archivo:** adjunte un `.qif` o un `.xls` con el formato FICOHSA soportado.
- **Diario en Odoo (destino):** seleccione el diario bancario configurado en el apartado 4.
- **Permitir reimportación** (si está disponible): solo si acepta riesgo de volver a procesar movimientos ya importados; el sistema intenta no duplicar gracias a `unique_import_id`, pero el uso consciente de esta opción evita sorpresas.

Tras cargar el archivo, el asistente puede mostrar resumen: rango de fechas, número de movimientos, sumas aproximadas, etc.

### 6.2. Botones principales (orden típico)

1. **Analizar con IA** — parsea el archivo, puede llamar a OpenAI para metadatos y análisis, y prepara sugerencias y detección de duplicados. Mientras dura, puede mostrarse un **indicador de progreso** en el cliente web.
2. **Emparejar diario Odoo** — si el extracto y el diario no coinciden por nombre o número de cuenta, use esta acción para alinear criterios antes de aplicar cambios.
3. Tras el estado **Analizado**:
   - **Aplicar Todo** — aplica el conjunto de acciones propuestas (importación y creación/actualización de modelos de conciliación, según lo que implemente su versión).
   - **Solo Crear Modelos** — genera o actualiza modelos de conciliación sin forzar toda la importación masiva, si no desea mezclar ambos en un solo paso.
   - **Solo Importar Líneas** — crea las líneas de extracto en Odoo sin el resto de acciones de modelos.
4. Los estados en la barra de estado (borrador / analizando / analizado / hecho) guían en qué momento puede usar cada botón.

Si algo falla, revise el registro de Odoo o el mensaje en pantalla; problemas frecuentes: API key inválida, cuota de OpenAI, archivo XLS que no cumple el layout FICOHSA, o diario no configurado para importación QIF.

---

## 7. Otras pantallas del módulo

En **Contabilidad → Transacciones** (junto al asistente) puede encontrar:

| Menú | Uso |
|------|-----|
| **Historial importaciones QIF** | Consulta de importaciones anteriores, trazabilidad y adjuntos asociados. |
| Conocimiento / sugerencias (según menús instalados) | **Conocimiento por diario** y **Sugerencias** alimentan el contexto que la IA o las reglas usan para proponer modelos; el administrador o usuario avanzado puede mantener textos o patrones utiles. |

Use el historial para auditar *qué* se importó y *cuándo*.

---

## 8. Importación “clásica” solo QIF (sin pasar por el asistente IA)

El módulo extiende el diario con **importación de extractos en formato QIF** compatible con el flujo estándar de “archivo / extracto bancario” de Odoo Community (sin depender de `accountant` ni módulos Enterprise de import bancario). Si solo necesita subir un QIF al diario, puede usar el flujo de importación de extractos de ese diario, siempre con la fuente de extractos y opciones QIF correctas. El asistente con IA añade el análisis, duplicados y modelos sugeridos.

---

## 9. Problemas frecuentes

| Síntoma | Qué comprobar |
|--------|----------------|
| “No se reconoce el formato” al importar en el diario | Que el archivo sea QIF válido (cabecera `!Type:`) o XLS con layout FICOHSA. |
| Error al abrir XLS | Que sea `.xls` legible por `xlrd` (no confundir con `.xlsx` en versiones que solo lean `.xls`). |
| No aparece análisis con IA | API key, modelo, conexión a internet, límites de la cuenta OpenAI. |
| Se duplican movimientos | Misma importación con distinto diario; reimport con **allow reimport** sin criterio; verifique `unique_import_id` y política de reimportación. |
| Fechas o importes incorrectos | Ajuste **formato de fecha** y **separador decimal** en el diario. |

---

## 10. Soporte y versiones

- Versión del módulo: véase el campo `version` en `__manifest__.py`.
- Mejoras o incidencias: contacte a su implementador o al equipo de **Grupo Nahuiik** según su contrato.

---

*Documento alineado con el comportamiento del módulo en Odoo 19 Community. Algunas etiquetas de menú pueden variar ligeramente según idioma y otros módulos instalados.*
