# -*- coding: utf-8 -*-


def post_init_hook(env):
    _set_cron_intervals(env)


def _set_cron_intervals(env):
    """Asegura intervalo de 6 horas en todos los crons de alertas."""
    specs = [
        'gn_due_alert_notifications.ir_cron_gn_due_alert_notifications',
        'gn_invoice_due_alerts.cron_invoice_due_alerts',
        'gn_customer_due_alerts.cron_customer_due_alerts',
    ]
    for xmlid in specs:
        cron = env.ref(xmlid, raise_if_not_found=False)
        if cron:
            cron.write({
                'interval_number': 6,
                'interval_type': 'hours',
            })
