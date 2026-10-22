#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para cargar los horarios de trabajo de Honduras manualmente
Ejecutar desde Odoo shell: python3 odoo-bin shell -d GRUPOHMM < load_calendars.py
"""

from odoo import api, SUPERUSER_ID

env = api.Environment(cr, SUPERUSER_ID, {})

# Horario 1: Lunes a jueves 8am-6pm, viernes 8am-5pm (44 horas semanales)
calendar1 = env['resource.calendar'].create({
    'name': 'Jornada 44h - Lunes a Jueves 8am-6pm, Viernes 8am-5pm',
    'company_id': False,
    'hours_per_day': 8.8,
    'attendance_ids': [
        (0, 0, {'name': 'Lunes Mañana', 'dayofweek': '0', 'hour_from': 8.0, 'hour_to': 12.0, 'day_period': 'morning'}),
        (0, 0, {'name': 'Lunes Tarde', 'dayofweek': '0', 'hour_from': 13.0, 'hour_to': 18.0, 'day_period': 'afternoon'}),
        (0, 0, {'name': 'Martes Mañana', 'dayofweek': '1', 'hour_from': 8.0, 'hour_to': 12.0, 'day_period': 'morning'}),
        (0, 0, {'name': 'Martes Tarde', 'dayofweek': '1', 'hour_from': 13.0, 'hour_to': 18.0, 'day_period': 'afternoon'}),
        (0, 0, {'name': 'Miércoles Mañana', 'dayofweek': '2', 'hour_from': 8.0, 'hour_to': 12.0, 'day_period': 'morning'}),
        (0, 0, {'name': 'Miércoles Tarde', 'dayofweek': '2', 'hour_from': 13.0, 'hour_to': 18.0, 'day_period': 'afternoon'}),
        (0, 0, {'name': 'Jueves Mañana', 'dayofweek': '3', 'hour_from': 8.0, 'hour_to': 12.0, 'day_period': 'morning'}),
        (0, 0, {'name': 'Jueves Tarde', 'dayofweek': '3', 'hour_from': 13.0, 'hour_to': 18.0, 'day_period': 'afternoon'}),
        (0, 0, {'name': 'Viernes Mañana', 'dayofweek': '4', 'hour_from': 8.0, 'hour_to': 12.0, 'day_period': 'morning'}),
        (0, 0, {'name': 'Viernes Tarde', 'dayofweek': '4', 'hour_from': 13.0, 'hour_to': 17.0, 'day_period': 'afternoon'}),
    ],
})

# Registrar el external ID
env['ir.model.data'].create({
    'name': 'resource_calendar_hn_44h_lunes_jueves',
    'model': 'resource.calendar',
    'module': 'l10n_hn_hr_payroll',
    'res_id': calendar1.id,
})

print(f"✓ Horario 1 creado: {calendar1.name} (ID: {calendar1.id})")

# Horario 2: Lunes a viernes 8am-5pm, sábados 8am-12m (44 horas semanales)
calendar2 = env['resource.calendar'].create({
    'name': 'Jornada 44h - Lunes a Viernes 8am-5pm, Sábados 8am-12m',
    'company_id': False,
    'hours_per_day': 8.8,
    'attendance_ids': [
        (0, 0, {'name': 'Lunes Mañana', 'dayofweek': '0', 'hour_from': 8.0, 'hour_to': 12.0, 'day_period': 'morning'}),
        (0, 0, {'name': 'Lunes Tarde', 'dayofweek': '0', 'hour_from': 13.0, 'hour_to': 17.0, 'day_period': 'afternoon'}),
        (0, 0, {'name': 'Martes Mañana', 'dayofweek': '1', 'hour_from': 8.0, 'hour_to': 12.0, 'day_period': 'morning'}),
        (0, 0, {'name': 'Martes Tarde', 'dayofweek': '1', 'hour_from': 13.0, 'hour_to': 17.0, 'day_period': 'afternoon'}),
        (0, 0, {'name': 'Miércoles Mañana', 'dayofweek': '2', 'hour_from': 8.0, 'hour_to': 12.0, 'day_period': 'morning'}),
        (0, 0, {'name': 'Miércoles Tarde', 'dayofweek': '2', 'hour_from': 13.0, 'hour_to': 17.0, 'day_period': 'afternoon'}),
        (0, 0, {'name': 'Jueves Mañana', 'dayofweek': '3', 'hour_from': 8.0, 'hour_to': 12.0, 'day_period': 'morning'}),
        (0, 0, {'name': 'Jueves Tarde', 'dayofweek': '3', 'hour_from': 13.0, 'hour_to': 17.0, 'day_period': 'afternoon'}),
        (0, 0, {'name': 'Viernes Mañana', 'dayofweek': '4', 'hour_from': 8.0, 'hour_to': 12.0, 'day_period': 'morning'}),
        (0, 0, {'name': 'Viernes Tarde', 'dayofweek': '4', 'hour_from': 13.0, 'hour_to': 17.0, 'day_period': 'afternoon'}),
        (0, 0, {'name': 'Sábado Mañana', 'dayofweek': '5', 'hour_from': 8.0, 'hour_to': 12.0, 'day_period': 'morning'}),
    ],
})

# Registrar el external ID
env['ir.model.data'].create({
    'name': 'resource_calendar_hn_44h_lunes_sabado',
    'model': 'resource.calendar',
    'module': 'l10n_hn_hr_payroll',
    'res_id': calendar2.id,
})

print(f"✓ Horario 2 creado: {calendar2.name} (ID: {calendar2.id})")
print("\n✅ Ambos horarios han sido creados exitosamente!")
