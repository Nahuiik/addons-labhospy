======================
l10n_hn_ia - AI Quotation Assistant
======================

Localización de Honduras - Asistente de Cotización con IA
==========================================================

Este módulo proporciona sugerencias de IA para cotizaciones de ventas.

Características
---------------

* Sugerencias de precios basadas en IA
* Recomendaciones inteligentes de productos
* Análisis de cotizaciones utilizando IA
* Integración con agentes de IA para asistencia en cotizaciones

Instalación
-----------

1. Copie el módulo en el directorio de addons de Odoo
2. Actualice la lista de módulos desde la interfaz de Odoo
3. Instale el módulo desde Aplicaciones > Localización > Honduras

Uso
---

1. Abra una cotización de venta existente o cree una nueva
2. En la sección "AI Suggestion", haga clic en el botón "Get AI Suggestion"
3. El sistema generará sugerencias de IA basadas en la cotización
4. Las sugerencias aparecerán en el campo de texto "AI Suggestion"

Integración con Servicios de IA
--------------------------------

El módulo incluye una implementación mock (simulada) de IA. Para integrar con un servicio de IA real, debe modificar el método `_invoke_ia_agent()` en el archivo `models/sale_order.py`.

Ejemplo de integración con OpenAI:

.. code-block:: python

    import openai
    
    def _invoke_ia_agent(self, context):
        self.ensure_one()
        
        # Configurar API key
        openai.api_key = self.env['ir.config_parameter'].sudo().get_param('openai.api_key')
        
        # Preparar prompt
        prompt = f"""
        Analiza la siguiente cotización y proporciona sugerencias:
        Cliente: {context.get('customer')}
        Total: {context.get('amount_total')}
        Productos: {context.get('order_lines')}
        
        Proporciona sugerencias sobre:
        - Precios competitivos
        - Oportunidades de descuento
        - Términos de pago recomendados
        - Productos relacionados
        """
        
        # Llamar a OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un asistente experto en análisis de cotizaciones comerciales."},
                {"role": "user", "content": prompt}
            ]
        )
        
        suggestion = response.choices[0].message.content
        
        return {
            'success': True,
            'suggestion': suggestion,
            'confidence': 0.85,
            'recommendations': [],
        }

Ejemplo de integración con Google AI:

.. code-block:: python

    import google.generativeai as genai
    
    def _invoke_ia_agent(self, context):
        self.ensure_one()
        
        # Configurar API key
        genai.configure(api_key=self.env['ir.config_parameter'].sudo().get_param('google.ai.api_key'))
        
        # Crear modelo
        model = genai.GenerativeModel('gemini-pro')
        
        # Preparar prompt
        prompt = f"""
        Analiza la siguiente cotización y proporciona sugerencias:
        Cliente: {context.get('customer')}
        Total: {context.get('amount_total')}
        Productos: {context.get('order_lines')}
        """
        
        # Generar respuesta
        response = model.generate_content(prompt)
        
        return {
            'success': True,
            'suggestion': response.text,
            'confidence': 0.85,
            'recommendations': [],
        }

Configuración
-------------

El módulo puede configurarse mediante parámetros del sistema (ir.config_parameter):

* `l10n_hn_ia.enabled`: Habilita/deshabilita las sugerencias de IA (por defecto: True)
* `l10n_hn_ia.api_key`: API key para el servicio de IA
* `l10n_hn_ia.model`: Modelo de IA a utilizar

Estructura del Módulo
---------------------

::

    l10n_hn_ia/
    ├── __init__.py
    ├── __manifest__.py
    ├── models/
    │   ├── __init__.py
    │   └── sale_order.py
    ├── views/
    │   └── sale_order_views.xml
    ├── security/
    │   └── ir.model.access.csv
    └── README.rst

Campos Agregados
----------------

* `ia_suggestion_text`: Texto de la sugerencia de IA
* `ia_suggestion_date`: Fecha de generación de la sugerencia
* `ia_suggestion_state`: Estado de la sugerencia (pending, processing, completed, error)
* `ia_enabled`: Habilita/deshabilita las sugerencias de IA para esta cotización

Métodos Principales
-------------------

* `get_ia_suggestion()`: Método principal para obtener sugerencias de IA
* `_invoke_ia_agent()`: Método para invocar el agente de IA (debe ser sobrescrito para integración real)
* `_prepare_ia_context()`: Prepara el contexto para el agente de IA
* `action_get_ia_suggestion()`: Acción del botón para generar sugerencias

Licencia
--------

LGPL-3

Autor
-----

Grupo Nahuiik

Website
-------

http://gruponahuiik.com



