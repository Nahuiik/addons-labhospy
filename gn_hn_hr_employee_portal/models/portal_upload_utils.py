# -*- coding: utf-8 -*-
"""Utilidades para validación de adjuntos en el portal."""
from odoo import _
from odoo.exceptions import UserError


def validate_upload(file_storage, env, filename=None):
    """
    Valida un archivo subido según max_upload_mb y allowed_mimetypes.
    :param file_storage: objeto tipo FileStorage (Werkzeug) o similar con .read(), .content_type, .filename
    :param env: odoo env para leer config
    :param filename: nombre opcional si file_storage no tiene
    :raises UserError: si el archivo excede tamaño o mimetype no permitido
    """
    if not file_storage:
        return
    max_mb = int(env['ir.config_parameter'].sudo().get_param(
        'gn_hn_hr_employee_portal.max_upload_mb', 5
    ))
    allowed = (env['ir.config_parameter'].sudo().get_param(
        'gn_hn_hr_employee_portal.allowed_mimetypes',
        'application/pdf,image/jpeg,image/png,image/gif'
    ) or '').strip()
    allowed_list = [m.strip().lower() for m in allowed.split(',') if m.strip()]
    max_bytes = max_mb * 1024 * 1024
    data = file_storage.read()
    file_storage.seek(0)
    if len(data) > max_bytes:
        raise UserError(_(
            'El archivo "%s" excede el tamaño máximo permitido (%s MB).'
        ) % (getattr(file_storage, 'filename', filename) or 'archivo', max_mb))
    content_type = (getattr(file_storage, 'content_type', '') or '').strip().lower()
    if allowed_list and content_type and content_type not in allowed_list:
        raise UserError(_(
            'Tipo de archivo "%s" no permitido. Permitidos: %s'
        ) % (content_type, ', '.join(allowed_list)))
