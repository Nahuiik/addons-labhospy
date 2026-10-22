# GN Website Plexus

Módulo para Odoo 19 que agrega una animación en canvas tipo plexus como snippet del Website Builder. Permite ajustar parámetros mediante atributos `data-*` y también ofrece una página de ejemplo para embeber el efecto sin usar el snippet.

## Instalación
1. Copiar la carpeta `gn_website_plexus` dentro del directorio de addons de su instancia Odoo 19.
2. Actualizar la lista de módulos desde **Apps** y buscar "GN Website Plexus".
3. Instalar el módulo. Al finalizar, el snippet "Animación Plexus" aparecerá en la categoría Estructura del editor web.

## Uso del snippet
1. Abrir el editor del sitio web (`Website ➜ Go to Website ➜ Edit`).
2. En la categoría de snippets "Estructura" (o la categoría donde tenga agrupado el snippet), arrastrar **Animación Plexus** al lugar deseado.
3. El snippet inserta un `<section class="s-js-animation">` con un contenedor `.js-animation-container` que renderiza el canvas.
4. En modo editor (`Editar`), el snippet muestra un panel flotante con controles para ajustar en vivo:
   - `data-spot-radius` (int, px, predeterminado `160`)
   - `data-overlay-opacity` (float 0–1, predeterminado `0.82`)
   - `data-line-max-dist` (int, px, predeterminado `140`)
   - `data-particle-density` (float por cada 100 000 px², predeterminado `0.14`)
   - `data-theme` (`light` | `dark`, predeterminado `light`)

Los cambios en los atributos se reflejan en vivo sin necesidad de refrescar la página.

## Embeber la animación sin snippet
El módulo incluye la vista `gn_website_plexus.page_plexus` con la URL `/plexus-animation`. Esta vista hereda `website.layout` y llama al template del snippet directamente. Puede copiar esta vista como referencia para incluir la animación en cualquier plantilla propia:

```xml
<t t-call="website.layout">
    <div id="wrap">
        <t t-call="gn_website_plexus.snippet_animation"/>
    </div>
</t>
```

## Extender con librerías externas
La animación actual es puramente canvas 2D sin dependencias externas. Si en el futuro se quiere migrar a p5.js u otra librería:
1. Colocar los archivos de la librería en `static/lib/<libreria>`.
2. Registrar primero la librería en `__manifest__.py` dentro de los assets `web.assets_frontend` y `website.assets_editor` antes de `static/src/js/animation.js`.
3. Importar la librería en `animation.js` y adaptar la clase `JSAnimation`.
4. Documentar los cambios en este README.

## Puntos de extensión en `animation.js`
- `class JSAnimation`: clase principal que encapsula el ciclo de vida (montaje, desmontaje, resize y render).
- `refreshConfig()`: reacciona a cambios de atributos `data-*`, útil para conectar con un panel de opciones de snippet.
- `_buildParticles()` y `_updateParticles()`: lógica del sistema de partículas; pueden reemplazarse para variaciones de movimiento.
- `_render()`: controla los colores/tema, spotlight y conexiones; puede extenderse para añadir nuevos temas o botones como "Pausar" en modo editor.

## Grabación sugerida
Para la evidencia visual solicitada (gif/vídeo de 15–30s):
1. Iniciar el editor del sitio.
2. Arrastrar el snippet, mover el cursor para mostrar el spotlight.
3. Modificar uno de los atributos (por ejemplo, `data-spot-radius`).
4. Eliminar el snippet y confirmar que la animación se detiene.
