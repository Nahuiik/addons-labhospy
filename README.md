# LABHOSPY — Addons Odoo

Repositorio de módulos personalizados para Odoo **19** (Community y, cuando aplica, integración con rutas enterprise del entorno). El código de trabajo vive en este directorio y se carga como **addons-path** junto al core de Odoo.

## Entorno típico de desarrollo

| Elemento | Valor |
|----------|--------|
| **Addons de este repo** | `/home/odoo/src/labhospy` |
| **Base de datos (desarrollo)** | `LABHOSPY-TEST` |
| **Core Odoo** | (p. ej.) `/home/odoo/src/odoo/addons` |
| **Enterprise / temas** | según tu instalación |

### Actualizar un módulo tras cambios

```bash
python3 /home/odoo/src/odoo/odoo-bin \
  --addons-path=/home/odoo/src/odoo/addons,/home/odoo/src/enterprise,/home/odoo/src/themes,/home/odoo/src/labhospy \
  -d LABHOSPY-TEST \
  -u NOMBRE_MODULO \
  --stop-after-init
```

Sustituye `NOMBRE_MODULO` por el nombre técnico del addon (carpeta). Tras modificar un módulo, incrementa la versión en `__manifest__.py` y ejecuta el comando anterior; el proceso debe terminar con código de salida **0** y sin trazas de error.

## Contenido

Este repositorio agrupa muchos addons (contabilidad, localización, stock, integraciones, etc.). Cada módulo puede tener su propio `README.md` en su carpeta.

### Documentación destacada

- **[Análisis Estados de Cuenta con OpenAI](gn_qif_openai_reconcile/)** (`gn_qif_openai_reconcile`): importación QIF/XLS (FICOHSA), detección de duplicados y sugerencias de conciliación con IA. Ver **[Manual de usuario](gn_qif_openai_reconcile/MANUAL.md)**.

## Licencias

Cada módulo indica su licencia en `__manifest__.py` (por ejemplo OPL-1, LGPL-3, etc.). Respeta la licencia de cada addon al redistribuir o modificar.

## Autoría

Varios módulos están firmados por **Grupo Nahuiik** u otros autores según el manifiesto correspondiente.
