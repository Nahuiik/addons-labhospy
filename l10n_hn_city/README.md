Trae

Used 1 context

README.md 1-1

Necesito ver el archivo index.html del módulo l10n_sv_city para actualizar el README.md con la información más reciente.

l10n_sv_city\static\description\index.html :( 1 - 200 )

# Distritos y Municipios de Honduras
## Versión: 18.0.1.0.1
## Descripción
Este módulo para Odoo proporciona una localización para Honduras, para distritos y municipios organizados para facilitar la gestión de direcciones.

## Características
### Localización Geográfica Completa
- Lista completa de Departamentos y municipios de Honduras
- Interfaz adaptada a la terminología local (Municipios en lugar de Ciudad, Departamento en lugar de Estado)
- Oculta automáticamente el campo de código postal para direcciones de Honduras
- Filtrado inteligente de municipios según el departamento seleccionado
- Honduras configurado como país predeterminado para nuevos contactos
- Menú dedicado para administrar la lista de distritos
- Moneda HNL configurada por defecto para Honduras
### Mejoras de Usabilidad
- Selección automática de distrito : Al cambiar de departamento, el sistema selecciona automáticamente el primer municipio disponible, evitando valores incorrectos.
- Priorización de municipios : La lista desplegable de municipios muestra primero los de Honduras, facilitando la búsqueda sin necesidad de seleccionar antes el país.
- Valores predeterminados : Honduras se establece como país predeterminado para nuevos contactos, agilizando el proceso de creación.
- Interfaz intuitiva con etiquetas adaptadas al contexto salvadoreño
## Funcionamiento
Una vez instalado, el módulo:

- Cambia automáticamente las etiquetas de "Ciudad" a "Municipio" y "Estado" a "Departamento"
- Establece Honduras como país predeterminado en los formularios de contacto
- Oculta el campo de código postal cuando se selecciona Honduras como país
- Proporciona una lista filtrada de munucipios basada en el departamento seleccionado
- Selecciona automáticamente el primer municipio disponible al cambiar de departamento
- Muestra primero los departamentos de Honduras en las listas desplegables para facilitar la selección
Puede acceder a la lista completa de municipios desde el menú Contactos > Configuración > Localización > Ciudades.

## Instalación
1. Descargue el módulo y colóquelo en la carpeta de addons de Odoo
2. Actualice la lista de módulos
3. Busque e instale el módulo "Municipios / Departamentos de Honduras"
## Información Técnica
### Dependencias
- base
- base_address_extended
- contacts
### Compatibilidad
- Odoo 18.0
### Licencia
- LGPL-3
## Autor
Mario Matamoros
Email: ifnfo@gruponahuiik.com Web: https://www.gruponahuiik.com/