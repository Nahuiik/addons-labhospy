# gn_qif_openai_reconcile — Análisis de estados de cuenta con OpenAI

Módulo para **Odoo 19** (Community): importa estados de cuenta en **QIF** o **XLS** (formato FICOHSA), detecta movimientos duplicados y propone **modelos de conciliación** con ayuda de modelos de lenguaje (OpenAI).

## Requisitos

- Odoo 19, módulos `account`, `account_statement_base` (vistas y acciones de líneas de extracto en CE) y `bus`.
- Paquetes Python: `openai`, `xlrd` (ver `external_dependencies` en `__manifest__.py`).
- Clave de API de OpenAI configurada en Ajustes (ver manual).

## Documentación

- **[MANUAL.md](MANUAL.md)** — Manual de usuario: configuración, diarios, asistente, menús y buenas prácticas.

## Licencia

OPL-1 (ver manifiesto).

## Autor

Grupo Nahuiik
