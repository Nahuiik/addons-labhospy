# -*- coding: utf-8 -*-
# Copyright 2024 Jupetern

import logging
import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.release import major_version
from odoo.service.common import exp_version

_logger = logging.getLogger(__name__)

APPS_URL = 'https://apps.odoo.com'


class ModuleUpdateWizard(models.TransientModel):
    """Transient wizard to display available module updates from Odoo Apps."""

    _name = 'svn.module_update.wizard'
    _description = 'Module Update Checker Wizard'

    update_line_ids = fields.One2many('svn.module_update.line', 'wizard_id', string='Available Updates')
    update_count = fields.Integer(string='Updates Found', compute='_compute_update_count', store=False)

    @api.depends('update_line_ids')
    def _compute_update_count(self):
        for wiz in self:
            wiz.update_count = len(wiz.update_line_ids)

    # --- Core fetch logic -----------------------------------------------------

    def _is_third_party(self, rec: dict) -> bool:
        """Heuristic to exclude Odoo core modules from the check.
        You can loosen/tighten this rule as needed.
        """
        author = (rec.get('author') or '').strip().lower()
        name = (rec.get('name') or '').strip().lower()
        is_odoo_sa = author in {'odoo s.a.', 'odoo sa', 'odoo', 'odoo community'}
        is_base_pack = name.startswith(('base_', 'web_', 'mail', 'im_', 'bus', 'digest'))
        return (not is_odoo_sa) and (not is_base_pack)

    def _fetch_updates_from_odoo_store(self):
        """Call Odoo Apps JSON-RPC endpoint to retrieve update info for installed modules."""
        # Step 1: Get installed modules with all relevant fields
        installed_modules = self.env['ir.module.module'].search_read(
            [('state', '=', 'installed')], fields=['name', 'state', 'installed_version', 'latest_version', 'display_name', 'author']
        )
        if not installed_modules:
            raise UserError(_('No installed modules detected.'))

        # Step 2: Filter third-party (exclude Odoo core modules)
        include_core = bool(self.env.context.get('include_core_modules'))
        filtered_modules = [rec for rec in installed_modules if include_core or self._is_third_party(rec)]
        if not filtered_modules:
            raise UserError(_('No third-party modules were found to check.'))

        # Step 3: Build payload exactly as Odoo API expects
        modules_payload = {
            rec['name']: {
                'name': rec['name'],
                # NOTE: Incorrect field names !!
                #   installed_version refers the latest version (the one on disk)
                #   latest_version refers the installed version (the one in database)
                'installed_version': rec['latest_version'],
                'latest_version': rec['installed_version'],
                'state': rec['state'],
            }
            for rec in filtered_modules
        }

        payload = {
            'jsonrpc': '2.0',
            'method': 'call',
            'params': {
                'modules': modules_payload,
                'version': exp_version(),
            },
        }

        try:
            response = requests.post(
                f'{APPS_URL}/apps/embed/update',
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            if data.get('error'):
                raise UserError(_('Odoo Store API Error: %s') % data['error'].get('message', 'Unknown API error'))

            result = data.get('result', {})
            return result or {}

        except requests.exceptions.Timeout:
            raise UserError(_('Timeout while contacting Odoo Apps Store.'))
        except requests.exceptions.ConnectionError:
            raise UserError(_('Failed to connect to Odoo Apps Store. Check your internet connection.'))
        except Exception as e:
            _logger.exception('Unexpected error while checking module updates')
            raise UserError(_('Unexpected error: %s') % str(e))

    # --- Actions --------------------------------------------------------------

    @api.model
    def action_check_updates(self):
        """Entrypoint you call from Server Action or buttons to open the wizard."""
        wiz = self.create({})
        result_map = wiz._fetch_updates_from_odoo_store()

        # Build a lookup once for display_name (avoid O(n^2) scans)
        installed_map = {
            rec['name']: rec
            for rec in self.env['ir.module.module'].search_read(
                [('state', '=', 'installed')],
                fields=['name', 'display_name'],
            )
        }

        line_vals = []
        for mod_name, info in (result_map or {}).items():
            todo = info.get('todo')
            if todo not in ('to_update', 'to_download'):
                continue

            local = installed_map.get(mod_name, {})
            line_vals.append(
                {
                    'name': local.get('display_name') or mod_name,
                    'module_name': mod_name,
                    'current_version': info.get('version_local_running') or info.get('version_local_downloaded') or '',
                    'new_version': info.get('version_remote') or '',
                    'wizard_id': wiz.id,
                    'to_action': todo,
                }
            )
        if line_vals:
            self.env['svn.module_update.line'].create(line_vals)
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Update Complete'),
                    'message': _('All checked modules are up to date.'),
                },
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Available Module Updates'),
            'res_model': 'svn.module_update.wizard',
            'view_mode': 'form',
            'res_id': wiz.id,
            'target': 'new',
        }


class ModuleUpdateLine(models.TransientModel):
    """One row per module with an available update."""

    _name = 'svn.module_update.line'
    _description = 'Module Update Line'

    name = fields.Char(string='Module')
    wizard_id = fields.Many2one('svn.module_update.wizard', ondelete='cascade')
    module_name = fields.Char(string='Technical Name', readonly=True)
    display_name = fields.Char(string='Display Name', readonly=True)
    current_version = fields.Char(string='Installed Version', readonly=True)
    new_version = fields.Char(string='Latest Version', readonly=True)
    to_action = fields.Selection(
        selection=[('to_download', 'Download'), ('to_update', 'Update')],
        string='To Action',
        readonly=True,
    )

    def action_open_app_store(self):
        """Open the module page on Odoo Apps using validated URL structure."""
        if not self.module_name:
            raise UserError(_('Module technical name is missing.'))

        branch = major_version  # e.g. '19.0'
        direct_url = f'{APPS_URL}/apps/modules/{branch}/{self.module_name}/'
        fallback_url = f'{APPS_URL}/apps/themes/{branch}/{self.module_name}/'

        try:
            # lightweight HEAD request for validation
            res = requests.get(direct_url, timeout=5)
            url = direct_url if res.status_code == 200 else fallback_url
        except Exception:
            url = fallback_url

        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }
