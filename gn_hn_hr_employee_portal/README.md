# GN Honduras HR Employee Portal

Portal web para empleados (usuarios portal) con solicitudes RRHH, constancias, ausencias, asistencias y nóminas.

## Propósito

Permitir a los empleados acceder a un portal de autoservicio donde pueden:
- Ver y solicitar cambios en su perfil
- Aceptar políticas/documentos obligatorios
- Solicitar constancias de trabajo
- Gestionar ausencias/vacaciones (con simulador de saldo)
- Ver calendario personal de ausencias
- Ver asistencias, solicitar correcciones y (opcionalmente) registrar entrada/salida
- Ver y descargar nóminas
- Los jefes pueden ver ausencias del equipo, calendario del equipo y aprobar correcciones

## Instalación

1. Añadir el directorio de addons al path de Odoo
2. Actualizar lista de aplicaciones
3. Instalar el módulo "GN Honduras HR Employee Portal"

Dependencias: portal, website, hr, base_setup, hr_holidays, hr_attendance, hr_payroll

## Configuración

En Ajustes > Portal del Empleado:
- **Registro de asistencia desde portal**: Habilitar para que empleados registren entrada/salida (por defecto: deshabilitado)
- **Exportación CSV**: Habilitar exportaciones (Fase 2)
- **Calendario de equipo**: Mostrar calendario a jefes
- **Límites de adjuntos**: Tamaño máximo (MB) y MIME types permitidos

## Roles

- **Empleado (portal)**: Usuario con grupo "Usuario Portal Empleado", vinculado a un hr.employee
- **Jefe**: Empleado con subalternos (parent_id); puede ver ausencias del equipo
- **RRHH**: Usuarios internos con acceso a aprobar solicitudes

## Rutas principales

| Ruta | Descripción |
|------|-------------|
| /my/home | Redirige empleados a /my/employee |
| /my/employee | Dashboard del portal |
| /my/policies | Políticas a aceptar (obligatorias antes del portal) |
| /my/employee/profile | Perfil y solicitud de cambios |
| /my/requests | Centro unificado de solicitudes |
| /my/certificates | Solicitudes de constancias |
| /my/leaves | Ausencias/vacaciones |
| /my/leaves/new | Nueva solicitud (con simulador de días/saldo) |
| /my/leaves/simulate | JSON: simular días y saldo disponible |
| /my/calendar | Calendario personal de ausencias |
| /my/attendances | Asistencias |
| /my/attendances/corrections | Solicitudes de corrección de asistencia |
| /my/payslips | Nóminas |
| /my/team/leaves | Ausencias del equipo (jefes) |
| /my/team/calendar | Calendario del equipo (jefes) |

## Invitación al portal

1. Crear usuario con tipo "Portal"
2. Asignar grupo "Usuario Portal Empleado"
3. El empleado debe tener work_email igual al login del usuario, o user_id vinculado

## Limitaciones

- Los empleados solo ven sus propios datos
- Las descargas se registran en auditoría
- El punch de asistencia está deshabilitado por defecto

## Autor

Grupo Nahuiik - www.gruponahuiik.com - info@gruponahuiik.com

Fecha: 2 de marzo de 2026
