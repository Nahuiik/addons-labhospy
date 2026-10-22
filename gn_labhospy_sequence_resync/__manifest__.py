{
    "name": "GN LabHosPy - Resincronizacion de Secuencias",
    "summary": "Detecta y corrige secuencias desincronizadas con los asientos existentes.",
    "version": "19.0.1.0.0",
    "depends": [
        "account",
        "mail",
    ],
    "author": "Grupo Nahuiik",
    "website": "https://www.gruponahuiik.com",
    "license": "LGPL-3",
    "category": "Accounting/Tools",
    "description": """
Evita el error 'Ya existe otro asiento con el mismo nombre' que aparece cuando
la secuencia (ir.sequence) queda desalineada con los asientos ya creados
(tipicamente tras importaciones masivas o creaciones manuales).

Provee:

- Boton "Resincronizar con datos" en la ficha de ir.sequence:
  ajusta number_next al maximo numero real + 1, en la secuencia y sus rangos.
- Wizard "Auditar secuencias contables" desde Configuracion > Tecnico > Secuencias:
  detecta TODAS las colisiones existentes y ofrece reparar en un solo clic.
- Cron mensual opcional que audita y notifica (desactivado por defecto).

Solo modifica ir.sequence.number_next_actual. NO renumera asientos existentes.
""",
    "data": [
        "security/ir.model.access.csv",
        "wizard/sequence_audit_wizard_views.xml",
        "views/ir_sequence_views.xml",
        "data/ir_cron.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
