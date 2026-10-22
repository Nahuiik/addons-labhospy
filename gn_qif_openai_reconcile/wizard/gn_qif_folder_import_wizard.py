# -*- coding: utf-8 -*-
import html
import os
import shutil
import tempfile

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class GnQifFolderImportWizard(models.TransientModel):
    """Recorre carpetas tipo «…/BANCOS/<banco>/*.xls(x)» y crea extractos por archivo."""

    _name = 'gn.qif.folder.import.wizard'
    _description = 'Importar extractos desde carpeta (lote Excel)'

    journal_id = fields.Many2one(
        'account.journal', string='Diario destino', required=True,
        domain="[('type', '=', 'bank')]",
        help='Todas las líneas nuevas irán al mismo diario. Repita con otro diario para otros bancos.',
    )
    folder_root = fields.Char(
        string='Carpeta base',
        help='Ruta en el servidor Odoo donde están los Excel, «Seleccionar carpeta…» sube desde su PC, '
             'o deje vacío para usar gn_qif.folder_import.root (p. ej. /home/odoo/zip/BANCOS).',
    )
    allow_reimport = fields.Boolean(string='Ignorar bloqueo de historial (misma huella/archivo repetido)')
    summary_html = fields.Html(string='Último informe', readonly=True)

    _icp_folder_key = 'gn_qif.folder_import.root'
    _fallback_folder = '/home/odoo/zip/BANCOS'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'folder_root' in fields_list and not res.get('folder_root'):
            res['folder_root'] = self.env['ir.config_parameter'].sudo().get_param(
                self._icp_folder_key,
                self._fallback_folder,
            )
        return res

    def _icp_fallback_root(self):
        return (
            self.env['ir.config_parameter'].sudo().get_param(
                self._icp_folder_key,
                self._fallback_folder,
            )
            or self._fallback_folder
        ).strip()

    def _validated_base_dir(self):
        raw = (self.folder_root or self._icp_fallback_root()).strip()
        if not raw or not os.path.isdir(raw):
            raise UserError(
                _('La carpeta «%s» no existe o no está accesible desde el proceso de Odoo.') % raw,
            )
        return os.path.realpath(os.path.abspath(raw))

    def _cleanup_temp_upload_bundle(self, path_abs):
        """Borra directorio creado por /gn_qif/folder_import/upload_tree para este usuario."""
        real = os.path.realpath(path_abs)
        parent = os.path.realpath(os.path.dirname(real))
        base_temp = os.path.realpath(tempfile.gettempdir())
        if parent != base_temp:
            return
        base_name = os.path.basename(real)
        prefix = 'gn_qif_bulk_%s_' % self.env.user.id
        if base_name.startswith(prefix):
            shutil.rmtree(real, ignore_errors=True)

    @staticmethod
    def _safe_child(base_real, relative):
        relative = relative.replace('\\', '/')
        combined = os.path.realpath(os.path.abspath(os.path.join(base_real, relative)))
        pref = base_real.rstrip(os.sep) + os.sep
        if combined != base_real and not combined.startswith(pref):
            raise UserError(_('Ruta no permitida: %s') % relative)
        return combined

    def _iter_statement_files(self, base_real):
        for fname in sorted(os.listdir(base_real)):
            lp = os.path.join(base_real, fname)
            if os.path.isfile(lp) and fname.lower().endswith(('.xlsx', '.xls')):
                yield fname.replace(os.sep, '/'), lp

        for sub in sorted(os.listdir(base_real)):
            subpath = os.path.join(base_real, sub)
            if not os.path.isdir(subpath):
                continue
            for fname in sorted(os.listdir(subpath)):
                if fname.startswith(('.', '~')):
                    continue
                rel_norm = '%s/%s' % (sub.replace(os.sep, '/'), fname)
                lp = self._safe_child(base_real, rel_norm)
                if os.path.isfile(lp) and fname.lower().endswith(('.xlsx', '.xls')):
                    yield rel_norm, lp

    def action_import_folder(self):
        self.ensure_one()
        base = self._validated_base_dir()
        wiz_model = self.env['qif.ai.wizard']

        scanned = list(self._iter_statement_files(base))
        if not scanned:
            self._cleanup_temp_upload_bundle(base)
            raise UserError(_(
                'No hay .xlsx ni .xls en %(path)s ni en una subcarpeta de primer nivel.', path=base,
            ))

        lines_ok = []
        lines_bad = []
        total_imported = 0

        try:
            for rel_label, abs_path in scanned:
                try:
                    with open(abs_path, 'rb') as handle:
                        raw = handle.read()
                    res = wiz_model.gn_bulk_import_statement(
                        self.journal_id,
                        raw,
                        filename=os.path.basename(abs_path),
                        allow_reimport=self.allow_reimport,
                    )
                    imp = int(res.get('imported_lines') or 0)
                    total_imported += imp
                    line = '%s [%s]' % (rel_label, res.get('file_format', '') or '?')
                    line += (' — %(n)d líneas nuevas; omitidas en hash %(h)d; duplicadas al crear %(c)d.') % {
                        'n': imp,
                        'h': int(res.get('ignored_duplicate_hash') or 0),
                        'c': int(res.get('skipped_create_duplicates') or 0),
                    }
                    lines_ok.append(html.escape(line))
                except UserError as err:
                    txt = err.args[0] if err.args else str(err)
                    lines_bad.append(html.escape('%s — %s' % (rel_label, txt)))
                except Exception as err:
                    lines_bad.append(html.escape('%s — %s' % (rel_label, str(err))))
        finally:
            self._cleanup_temp_upload_bundle(base)

        paras = []
        paras.append(html.escape(_('Directorio procesado %(p)s.') % {'p': base}))
        paras.append(html.escape(_('Archivos tratados %(n)d.') % {'n': len(scanned)}))
        paras.append(
            html.escape(
                _('Total líneas nuevas sumando extractos bien importados: %(n)d.') % {'n': total_imported},
            ),
        )
        if lines_bad:
            paras.append('<strong>%s</strong>' % html.escape(_('Incidencias')))
            paras.append('<br/>'.join(lines_bad))
            paras.append('<br/>')
        if lines_ok:
            paras.append('<strong>%s</strong>' % html.escape(_('Resumen')))
            paras.append('<br/>'.join(lines_ok))
        blob = ''.join('%s<br/><br/>' % p for p in paras)

        self.write({'summary_html': blob})

        return {
            'type': 'ir.actions.act_window',
            'name': _('Importar carpeta Excel'),
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': {'default_journal_id': self.journal_id.id},
            'views': [(False, 'form')],
        }
