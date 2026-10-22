# Odoo Monitor Console - Consola Central de Monitoreo

## Descripción

`odoo_monitor_console` es un módulo de Odoo 19 que proporciona una consola central para monitorear múltiples instancias Odoo remotas. Permite consolidar métricas de usuarios activos, dispositivos conectados y actividad en tiempo real desde una única interfaz.

## Características Principales

- **Registro y Gestión de Instancias**: Registra múltiples instancias Odoo remotas con configuración individual
- **Sincronización Automática**: Sincroniza métricas automáticamente cada 1-5 minutos mediante cron jobs
- **Dashboard Consolidado**: Visualiza KPIs y métricas de todas las instancias en un solo lugar
- **Usuarios Activos**: Lista consolidada de usuarios activos en la última hora desde todas las instancias
- **Multi-dispositivo**: Detecta y cuenta dispositivos distintos por usuario
- **Historial de Métricas**: Almacena snapshots históricos de métricas para análisis temporal
- **Compatibilidad Multi-versión**: Compatible con instancias Odoo 8, 11, 14, 17 y 19

## Requisitos

### Dependencias de Python

```bash
pip install requests
```

### Módulos de Odoo Requeridos

- `base`
- `web`

### Módulos Requeridos en Instancias Remotas

Cada instancia Odoo que desees monitorear debe tener instalado el módulo `odoo_instance_agent`.

## Instalación

1. Copia el módulo en tu directorio de addons:
   ```bash
   cp -r odoo_monitor_console /opt/odoo19/addons-odoo/
   ```

2. Actualiza la lista de aplicaciones en Odoo

3. Instala el módulo desde la interfaz de Odoo o mediante línea de comandos:
   ```bash
   python3 odoo-bin -u odoo_monitor_console -d tu_base_de_datos
   ```

## Configuración

### 1. Registrar una Instancia Remota

1. Ve a **Monitoreo Consola > Instancias**
2. Crea un nuevo registro con:
   - **Nombre**: Nombre descriptivo de la instancia
   - **URL**: URL base de la instancia (ej: `http://192.168.1.100:8069`)
   - **Token**: Token de seguridad configurado en la instancia remota
   - **Intervalo de Sincronización**: Minutos entre sincronizaciones (default: 5)
   - **Activa**: Marca si la instancia debe sincronizarse automáticamente

### 2. Configurar Token en Instancia Remota

En cada instancia remota que deseas monitorear:

1. Instala el módulo `odoo_instance_agent`
2. Ve a **Monitoreo > Configuración**
3. Configura el **Token de Seguridad**
4. Si dejas el token vacío, solo se permitirá acceso desde red local

### 3. Probar Conexión

1. Abre el formulario de la instancia
2. Haz clic en **"Probar Conexión"**
3. Verifica que la conexión sea exitosa antes de activar la sincronización automática

## Uso

### Dashboard de Instancias

Accede a **Monitoreo Consola > Dashboard** para ver:
- Estado de todas las instancias (En línea / Fuera de línea)
- Última sincronización
- Estado de la última sincronización (Éxito / Error)

### Usuarios Activos

Accede a **Monitoreo Consola > Usuarios Activos** para ver:
- Lista consolidada de usuarios activos en la última hora
- Tipo de usuario (Interno / Portal)
- Número de dispositivos por usuario
- Última actividad registrada
- Instancia donde está activo

### Historial de Métricas

Accede a **Monitoreo Consola > Historial de Métricas** para ver:
- Snapshots históricos de métricas por instancia
- Gráficos de evolución de usuarios activos
- Comparación entre usuarios Portal e Internos

## Modelos de Datos

### monitor.instance

Registra instancias Odoo remotas a monitorear.

**Campos principales:**
- `name`: Nombre descriptivo
- `url`: URL base de la instancia
- `token`: Token de seguridad
- `version`: Versión de Odoo detectada (readonly)
- `is_online`: Estado online/offline (computed)
- `last_sync`: Fecha de última sincronización
- `last_sync_status`: Estado de última sincronización

### monitor.user_snapshot

Almacena snapshots históricos de métricas por instancia.

**Campos principales:**
- `instance_id`: Instancia relacionada
- `snapshot_date`: Fecha del snapshot
- `users_total`: Total de usuarios
- `active_last_hour_total`: Activos en última hora
- `portal_total` / `internal_total`: Totales por tipo

### monitor.user_activity_line

Almacena detalles de usuarios activos por instancia.

**Campos principales:**
- `instance_id`: Instancia relacionada
- `user_login`: Login del usuario
- `user_type`: Tipo (internal/portal)
- `devices_count`: Número de dispositivos
- `last_activity`: Última actividad registrada

## Endpoints de API

El módulo consume los siguientes endpoints de `odoo_instance_agent`:

### GET /monitoring/users_status

Obtiene estado de usuarios de una instancia.

**Parámetros:**
- `window`: Minutos de ventana (default: 60)
- `token`: Token de seguridad

**Respuesta:**
```json
{
  "instance": {
    "name": "database_name",
    "version": "19.0",
    "db": "database_name",
    "hostname": "server-name"
  },
  "totals": {
    "users_total": 100,
    "users_active": 80,
    "portal_total": 30,
    "internal_total": 50
  },
  "active_last_hour": {
    "total": 25,
    "portal": 10,
    "internal": 15
  },
  "active_users": [...]
}
```

## Sincronización Automática

El módulo incluye un cron job que sincroniza todas las instancias activas cada 5 minutos por defecto.

**Configuración del Cron:**
- Archivo: `data/ir_cron.xml`
- Intervalo: 5 minutos (configurable)
- Método: `monitor.instance.sync_all_instances()`

## Seguridad

### Grupos de Usuarios

- **Usuario** (`group_monitor_console_user`): Acceso de solo lectura a datos de monitoreo
- **Administrador** (`group_monitor_console_admin`): Acceso completo a configuración y datos

### Autenticación

- Los endpoints requieren token de seguridad configurado en cada instancia
- Si no hay token, solo se permite acceso desde red local (IPs privadas)
- Las peticiones se realizan con timeout de 30 segundos

## Métodos Principales

### monitor.instance.sync_instance()

Sincroniza métricas desde una instancia remota específica.

**Retorna:**
```python
{
    'success': True/False,
    'data': {...},  # Si success=True
    'error': 'mensaje'  # Si success=False
}
```

### monitor.user_activity_line.get_consolidated_active_users()

Obtiene lista consolidada de usuarios activos de todas las instancias.

**Parámetros:**
- `window_minutes`: Ventana de tiempo en minutos (default: 60)

**Retorna:** Lista de diccionarios con usuarios consolidados

### monitor.user_activity_line.get_top_users_by_devices()

Obtiene ranking de usuarios con más dispositivos conectados.

**Parámetros:**
- `limit`: Número máximo de usuarios (default: 10)

**Retorna:** Lista ordenada por número de dispositivos

## Pruebas

El módulo incluye pruebas funcionales en `tests/test_monitor_instance.py`:

- `test_create_instance`: Crear instancia
- `test_unique_url_constraint`: Constraint de URL única
- `test_compute_is_online`: Cálculo de estado online
- `test_sync_instance_success`: Sincronización exitosa
- `test_sync_instance_error`: Manejo de errores
- `test_sync_instance_timeout`: Manejo de timeout
- `test_create_snapshot`: Creación de snapshots
- `test_create_activity_lines`: Creación de líneas de actividad
- `test_get_consolidated_active_users`: Usuarios consolidados
- `test_get_top_users_by_devices`: Ranking por dispositivos

**Ejecutar pruebas:**
```bash
python3 odoo-bin --test-enable --test-tags=odoo_monitor_console -d tu_base_de_datos
```

## Troubleshooting

### La instancia no se sincroniza

1. Verifica que la instancia remota tenga `odoo_instance_agent` instalado
2. Verifica que el token sea correcto
3. Verifica conectividad de red entre servidores
4. Revisa el campo "Último Error" en el formulario de la instancia

### Error "Token inválido"

1. Verifica que el token en la consola coincida con el configurado en la instancia remota
2. Si el token está vacío en la instancia remota, verifica que la IP del servidor consola esté en la red local

### La instancia aparece como "Fuera de línea"

1. Verifica que la última sincronización haya sido exitosa
2. Verifica que el intervalo de sincronización no sea muy largo
3. Revisa los logs de Odoo para errores de conexión

## Licencia

LGPL-3

## Autor

Sistema de Monitoreo

## Versión

19.0.1.0.0

## Soporte

Para reportar problemas o solicitar funcionalidades, contacta al equipo de desarrollo.
