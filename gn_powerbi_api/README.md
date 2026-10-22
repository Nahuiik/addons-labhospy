# Power BI Connector para Odoo 19

Módulo de integración completo con Microsoft Power BI para Odoo 19, desarrollado por Grupo Nahuiik.

## Descripción

Este módulo permite integrar Odoo 19 con Microsoft Power BI, proporcionando:

- Configuración de conexión segura con Azure AD OAuth2
- Administración de Workspaces, Datasets y Tablas de Power BI
- Exportación manual y automática de datos desde cualquier modelo de Odoo
- Sincronización incremental basada en create_date y write_date
- Gestión de plantillas de tablas y clonado de configuraciones
- Métricas, logs y alertas para monitoreo
- Monitor de salud en tiempo real
- Versionado de esquemas de datasets y tablas

## Requisitos

- Odoo 19.0 o superior
- Módulos base: `base`, `web`, `mail`
- Python: librería `requests` (se instala automáticamente)

## Instalación

1. Copiar el módulo en la carpeta de addons de Odoo
2. Actualizar la lista de aplicaciones
3. Instalar el módulo "Power BI Connector"

## Configuración

1. Ir a Power BI > Conexión
2. Crear una nueva conexión con las credenciales de Azure AD:
   - Tenant ID
   - Client ID
   - Client Secret
   - Redirect URI
3. Hacer clic en "Probar Conexión" para validar
4. Activar la conexión

## Uso Básico

1. **Importar Workspaces**: Power BI > Workspaces > Sincronizar desde Power BI
2. **Crear Dataset**: Power BI > Datasets > Crear nuevo dataset
3. **Agregar Tablas**: En el dataset, agregar tablas asociadas a modelos de Odoo
4. **Configurar Campos**: Seleccionar los campos a exportar y sus tipos
5. **Publicar Dataset**: Hacer clic en "Publicar en Power BI"
6. **Exportar Datos**: En la tabla, hacer clic en "Exportar Datos"

## Características Principales

### Exportación Incremental
- Filtra registros nuevos y modificados basándose en `create_date` y `write_date`
- Configurable por tabla
- Actualiza automáticamente `last_sync_datetime`

### Exportación Automática
- Configurar cron por tabla
- Modo incremental o completo
- Ejecución automática cada 15 minutos (configurable)

### Métricas y Alertas
- Registro automático de métricas por exportación
- Alertas configurables por umbrales
- Notificaciones por chatter, email o notificación interna

### Plantillas
- Guardar configuración de tablas como plantillas
- Crear nuevas tablas desde plantillas
- Reutilizar configuraciones comunes

## Permisos

- **Power BI User**: Lectura de datos exportados y métricas
- **Power BI Officer**: Crear/editar datasets, tablas y ejecutar exportaciones
- **Power BI Manager**: Acceso completo, incluyendo configuración de conexión

## Soporte

Para soporte técnico, contactar a Grupo Nahuiik.

## Licencia

LGPL-3

