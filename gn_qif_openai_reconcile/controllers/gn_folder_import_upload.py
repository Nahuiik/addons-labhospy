# -*- coding: utf-8 -*-
"""Subida de árbol de archivos desde el navegador (wizard importar carpeta)."""

import logging
import os
import posixpath
import secrets
import shutil
import tempfile

from werkzeug.datastructures import FileStorage

from odoo import _, http
from odoo.http import request

_logger = logging.getLogger(__name__)

EXCEL_SUFFIXES = ('.xlsx', '.xls')


def _gn_upload_safe_target(base_abs: str, relative_name: str) -> str:
    """Devuelve ruta segura dentro de ``base_abs`` para escribir un archivo."""
    rel = relative_name.replace('\\', '/').strip()
    parts = []
    for seg in rel.split('/'):
        if seg in ('', '.'):
            continue
        if seg == '..':
            raise ValueError('parent segment')
        if os.sep in seg:
            raise ValueError('embedded sep')
        parts.append(seg)
    if not parts:
        raise ValueError('empty')

    normed = posixpath.normpath('/'.join(parts)).lstrip('/')
    if not normed:
        raise ValueError('normalized empty')
    if '..' in normed.split('/') or normed.startswith('../'):
        raise ValueError('traversal')

    target = os.path.realpath(os.path.join(base_abs, *normed.split('/')))
    pref = os.path.realpath(base_abs).rstrip(os.sep) + os.sep
    base_real_single = os.path.realpath(base_abs)
    ok = target == base_real_single or target.startswith(pref)
    if not ok:
        raise ValueError('outside base')
    return target


class GnFolderImportUpload(http.Controller):
    """Guarda ficheros .xls(x) enviados con rutas relativas (p. ej. webkitRelativePath)."""

    @http.route(
        '/gn_qif/folder_import/upload_tree',
        type='http',
        auth='user',
        methods=['POST'],
        csrf=True,
    )
    def upload_tree(self, **kwargs):
        if not request.env.user.has_group('account.group_account_user'):
            return request.make_json_response(
                {'error': _('No tiene permisos para importar extractos.')},
                status=403,
            )
        uploads = request.httprequest.files.getlist('ufile')
        if not uploads:
            return request.make_json_response({'error': _('No se recibieron archivos.')}, status=400)

        token = secrets.token_hex(12)
        base = os.path.join(
            tempfile.gettempdir(),
            'gn_qif_bulk_%s_%s' % (request.env.user.id, token),
        )
        try:
            os.makedirs(base, mode=0o700, exist_ok=False)
        except OSError as err:
            _logger.warning('mkdir gn_qif upload base failed: %s', err)
            return request.make_json_response(
                {'error': _('No se pudo crear un directorio temporal en el servidor.')},
                status=500,
            )

        excel_stored = 0

        try:
            for uf in uploads:
                if not isinstance(uf, FileStorage) or not uf.filename:
                    continue
                fname = uf.filename.strip()
                if not fname.lower().endswith(EXCEL_SUFFIXES):
                    continue
                try:
                    target = _gn_upload_safe_target(base, fname)
                except ValueError:
                    shutil.rmtree(base, ignore_errors=True)
                    return request.make_json_response(
                        {'error': _('Nombre de archivo no permitido: %s') % fname},
                        status=400,
                    )
                dirname = os.path.dirname(target)
                if dirname != os.path.realpath(base):
                    os.makedirs(dirname, mode=0o700, exist_ok=True)
                uf.save(target)
                excel_stored += 1

            if excel_stored == 0:
                shutil.rmtree(base, ignore_errors=True)
                return request.make_json_response(
                    {'error': _('La carpeta no contiene archivos .xlsx ni .xls.')},
                    status=400,
                )

            return request.make_json_response({'folder_root': base, 'excel_count': excel_stored})
        except Exception as err:
            shutil.rmtree(base, ignore_errors=True)
            _logger.exception('upload_tree failed')
            return request.make_json_response({'error': str(err)}, status=500)
