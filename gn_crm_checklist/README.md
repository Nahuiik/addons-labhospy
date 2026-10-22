# GN CRM Checklist

## Descripción

Módulo de Checklist y Aprobación para Leads y Oportunidades CRM en Odoo 19.0.

Este módulo permite crear y gestionar checklists personalizados para Leads y Oportunidades en CRM, facilitando el seguimiento de tareas y pasos necesarios para completar cada oportunidad.

## Características Principales

* **Menú separado para Checklists**: Crea y gestiona checklists desde un menú dedicado en CRM
* **Múltiples Checklists por Lead**: Vincula múltiples checklists a un mismo Lead u Oportunidad
* **Items de Checklist**: Define items individuales dentro de cada checklist con secuencia personalizable
* **Completar/Cancelar Items**: Marca items como completados o cancélalos según sea necesario
* **Porcentaje de Progreso**: Visualiza el progreso del checklist como porcentaje basado en items completados
* **Vista Kanban**: El porcentaje de progreso se muestra en la vista Kanban de Leads y Oportunidades
* **Control de Acceso**: Solo usuarios con permisos pueden completar o cancelar items del checklist

## Instalación

1. Copia el módulo en tu directorio de addons de Odoo
2. Actualiza la lista de aplicaciones en Odoo
3. Instala el módulo "GN CRM Checklist"

## Uso

### Crear un Checklist

1. Ve a **CRM → Checklists CRM**
2. Haz clic en **Nuevo**
3. Ingresa el nombre y descripción del checklist
4. En la pestaña "Items del Checklist", agrega los items que deben completarse
5. Define la secuencia de cada item arrastrándolo con el manejador

### Agregar Checklist a un Lead

1. Abre un Lead u Oportunidad
2. Ve a la pestaña **Checklists**
3. Haz clic en **Agregar Checklist**
4. Selecciona el checklist que deseas agregar
5. Los items del checklist aparecerán automáticamente

### Completar Items

1. En la pestaña Checklists del Lead, marca los items como completados usando el toggle
2. O usa los botones **Completar Todo** o **Cancelar Todo** para cambiar todos los items a la vez

### Visualizar Progreso

El porcentaje de progreso se muestra:
- En el header del formulario del Lead (barra de progreso)
- En la pestaña Checklists
- En la vista Kanban de Leads y Oportunidades

## Permisos

El módulo incluye dos grupos de seguridad:

- **Usuario de Checklist CRM**: Puede ver y completar/cancelar items de checklist
- **Administrador de Checklist CRM**: Puede crear, editar y eliminar checklists e items

## Requisitos

- Odoo 19.0
- Módulo CRM (`crm`)
- Módulo Mail (`mail`)

## Autor

Grupo Nahuiik
Website: https://www.gruponahuiik.com

## Licencia

LGPL-3

## Versión

1.0.0


