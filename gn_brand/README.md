# GN Brand

## Descripción

El módulo **GN Brand** permite personalizar el texto que aparece en el systray (barra superior) de Odoo mediante un campo personalizado en la configuración de la empresa.

## Características Principales

- **Campo Personalizado**: Agrega un campo "Nombre Systray" en la configuración de la empresa
- **Personalización**: Permite escribir un texto personalizado que se mostrará en el systray
- **Reemplazo Automático**: El texto ingresado reemplaza automáticamente el nombre de la empresa en el systray
- **Sin Configuración Adicional**: Funciona inmediatamente después de configurar el campo

## Instalación

1. Copia el módulo en la carpeta de addons de Odoo
2. Actualiza la lista de aplicaciones
3. Instala el módulo desde el menú de **Aplicaciones**

## Uso

### Configurar el Nombre del Systray

1. Ve a **Configuración → Usuarios y Compañías → Compañías**
2. Selecciona o edita la compañía deseada
3. En el formulario de la compañía, encontrarás el campo **"Nombre Systray"**
4. Ingresa el texto que deseas mostrar en el systray
5. Guarda los cambios

El texto ingresado aparecerá automáticamente en el systray (barra superior) en lugar del nombre de la empresa.

## Requisitos

- Odoo 19.0 o superior
- Módulos `web` y `base` (incluidos por defecto)

## Compatibilidad

Este módulo está diseñado para Odoo 19.0 y utiliza las características modernas de la plataforma:
- Utiliza el sistema de patching de Odoo para modificar el comportamiento del NavBar
- Compatible con el sistema de assets moderno de Odoo
- No interfiere con otros módulos

## Autor

**Grupo Nahuiik**
- Website: https://www.gruponahuiik.com

## Licencia

LGPL-3

## Versión

1.0.0

## Soporte

Para soporte técnico, contacta a Grupo Nahuiik.

## Notas Técnicas

- El módulo agrega un campo `systray_name` al modelo `res.company`
- Utiliza JavaScript para reemplazar dinámicamente el texto en el systray
- Se utiliza un MutationObserver para detectar y actualizar elementos que se agreguen dinámicamente al DOM
- Si el campo está vacío, se muestra el nombre de la empresa por defecto
