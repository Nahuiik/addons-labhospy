# Notificaciones visuales de vencimiento (CxP / CxC)

Módulo compartido para **Odoo 19** que añade tarjetas interactivas en tiempo real
sobre los módulos existentes:

- `gn_invoice_due_alerts` (cuentas por pagar)
- `gn_customer_due_alerts` (cuentas por cobrar)

## Instalación

```bash
python3 /home/odoo/src/odoo/odoo-bin \
  --addons-path=/home/odoo/src/odoo/addons,/home/odoo/src/labhospy \
  --data-dir=/home/odoo/data/labhospy \
  -d LABHOSPY \
  -i gn_due_alert_notifications \
  --stop-after-init
```

## Actualización

```bash
python3 /home/odoo/src/odoo/odoo-bin \
  --addons-path=/home/odoo/src/odoo/addons,/home/odoo/src/labhospy \
  --data-dir=/home/odoo/data/labhospy \
  -d LABHOSPY \
  -u gn_due_alert_notifications \
  --stop-after-init
```

## Crons (intervalo 6 horas)

| Cron | Intervalo | Función |
|------|-----------|---------|
| Alertas visuales: evaluar vencimientos | 6 h | Tarjetas RT + apuntes CxC |
| Alertas de vencimiento proveedor | 6 h | Correo resumen CxP |
| Alertas de vencimiento clientes | 6 h | Correo resumen CxC |

El **resumen diario por correo** se envía en la **primera ejecución del cron
después de la hora configurada** (`gn_due_notif_daily_summary_hour`, default 8:00),
una sola vez por día y por compañía.

## Configuración

Contabilidad → Ajustes → **Notificaciones visuales de vencimiento**

## Alertas CxC (apuntes)

Incluye apuntes abiertos en cuentas `asset_receivable` de asientos `entry`
(saldos iniciales MISCE, 1010201.02, etc.). Las tarjetas muestran **Saldo CxC**
y no ofrecen «Registrar pago» (solo abrir asiento).

## Pruebas locales

```bash
python3 /home/odoo/src/odoo/odoo-bin \
  --addons-path=/home/odoo/src/odoo/addons,/home/odoo/src/labhospy \
  --data-dir=/home/odoo/data/labhospy \
  -d LABHOSPY \
  --test-enable \
  --test-tags=gn_due_alert_notifications \
  --stop-after-init
```

## CI

Workflow GitHub Actions: `.github/workflows/gn_due_alert_notifications.yml`
