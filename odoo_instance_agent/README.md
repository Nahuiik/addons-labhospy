# Odoo Instance Agent - Monitoreo de Usuarios

Módulo agente para monitoreo de usuarios conectados en instancias Odoo.

## Características

- ✅ Tracking de usuarios activos/archivados
- ✅ Distinción entre usuarios Portal e Internos
- ✅ Monitoreo de actividad en última hora (configurable)
- ✅ Soporte multi-dispositivo por usuario
- ✅ Endpoints seguros para métricas y heartbeat
- ✅ Compatible con Odoo 8, 11, 14, 17, 19

## Instalación

1. Copiar el módulo a la carpeta de addons de Odoo
2. Actualizar la lista de aplicaciones
3. Instalar el módulo "Odoo Instance Agent - Monitoreo de Usuarios"

## Configuración

### 1. Configurar Token de Seguridad

Ir a **Configuración > Monitoreo > Configuración** y establecer un token de seguridad para proteger los endpoints.

Si se deja vacío, solo se permite acceso desde red local (IPs privadas).

### 2. Configurar Ventana de Actividad

Establecer la ventana de tiempo en minutos para considerar usuarios activos (default: 60 minutos).

### 3. Configurar Intervalo de Heartbeat

Establecer el intervalo en segundos para enviar heartbeat desde el navegador (default: 60 segundos).

## Endpoints

### POST /monitoring/heartbeat

Endpoint para recibir heartbeats de dispositivos.

**Payload:**
```json
{
    "device_id": "uuid-del-dispositivo",
    "user_id": 123
}
```

**Respuesta:**
```json
{
    "success": true,
    "device_id": "uuid-del-dispositivo",
    "last_seen": "2024-01-01T12:00:00",
    "user_type": "internal"
}
```

### GET /monitoring/users_status

Endpoint para obtener estado de usuarios.

**Parámetros:**
- `window`: minutos de ventana (default: 60)
- `token`: token de seguridad (opcional si viene en header X-Monitor-Token)

**Respuesta:**
```json
{
    "instance": {
        "name": "db_name",
        "version": "19.0",
        "db": "db_name",
        "hostname": "server",
        "timestamp": "2024-01-01T12:00:00"
    },
    "window_minutes": 60,
    "totals": {
        "users_total": 100,
        "users_active": 95,
        "users_archived": 5,
        "portal_total": 30,
        "internal_total": 70
    },
    "active_last_hour": {
        "total": 25,
        "portal": 10,
        "internal": 15
    },
    "active_users": [...]
}
```

### GET /monitoring/health

Endpoint simple de healthcheck.

**Respuesta:**
```json
{
    "status": "ok",
    "instance": {...}
}
```

## Uso

El módulo automáticamente:
1. Envía heartbeats periódicos desde cada navegador/dispositivo
2. Registra la presencia de usuarios
3. Mantiene estadísticas de usuarios activos

Para ver los datos:
- **Monitoreo > Presencia de Dispositivos**: Ver todos los registros de presencia
- **Configuración > Monitoreo**: Configurar parámetros

## Integración con Consola Central

Este módulo está diseñado para trabajar con el módulo `odoo_monitor_console` que consolida métricas de múltiples instancias.

Para conectar una instancia a la consola central:
1. Configurar el token en esta instancia
2. Registrar la instancia en la consola central con:
   - URL: http://ip-o-hostname:puerto
   - Token: el mismo token configurado aquí

