# l10n_hn_retentions

## Descripción
Módulo de localización para Odoo 19 que permite gestionar las retenciones
establecidas por la normativa hondureña. Incluye configuración por compañía,
cálculo automático al registrar pagos y reportes para documentar las deducciones.

## Características
- Configuración independiente para retenciones de proveedores y clientes.
- Cuentas contables y porcentajes parametrizables (1 %, 12.5 %, 15 %).
- Integración con el asistente de pagos para aplicar las retenciones de forma
  automática y generar los asientos correspondientes.
- Reporte en formato XLS listo para entregar a terceros o respaldar auditorías.
- Control de permisos para limitar quién puede aplicar cada tipo de retención.

## Instalación
1. Copia la carpeta `l10n_hn_retentions` en la ruta de addons de tu instancia.
2. Reinicia el servicio de Odoo.
3. Desde **Aplicaciones**, actualiza la lista e instala **Retenciones Honduras**.

## Configuración
1. Entra a **Facturación → Configuración → Ajustes**.
2. Busca la sección *Retenciones* y habilita las opciones necesarias.
3. Define las cuentas contables y porcentajes según las políticas de tu empresa.

## Uso
- Registra un pago de proveedor o cliente; el asistente mostrará los campos para
  aplicar las retenciones configuradas.
- Los montos se descuentan del pago, se generan los asientos contables y se
  conserva el historial en la ficha del partner.
- Puedes emitir el comprobante de retención desde el mismo pago.

## Créditos
Desarrollado por Grupo Nahuiik. Para soporte o mejoras visita
[gruponahuiik.com](https://www.gruponahuiik.com).

