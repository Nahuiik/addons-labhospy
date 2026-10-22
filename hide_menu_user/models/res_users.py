# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ResUsers(models.Model):
    _inherit = 'res.users'

    def write(self, vals):
        old_hide_menu_map = {record.id: record.hide_menu_ids for record in self}
        res = super().write(vals)
        for record in self:
            old_hide_menu_ids = old_hide_menu_map.get(record.id, self.env['ir.ui.menu'])
            for menu in record.hide_menu_ids:
                menu.sudo().write({'restrict_user_ids': [(4, record.id)]})
            removed_menus = old_hide_menu_ids - record.hide_menu_ids
            for menu in removed_menus:
                menu.sudo().write({'restrict_user_ids': [(3, record.id)]})
        return res

    def _get_is_admin(self):
        for rec in self:
            rec.is_admin = rec.id == self.env.ref('base.user_admin').id

    hide_menu_ids = fields.Many2many(
        'ir.ui.menu', string="Hidden Menu",
        help='Select menu items that need to be hidden to this user.')

    is_admin = fields.Boolean(
        compute='_get_is_admin', string="Is Admin",
        help='Check if the user is an admin.')

    is_show_specific_menu = fields.Boolean(
        string='Is Show Specific Menu',
        compute='_compute_is_show_specific_menu',
        help='Field to determine if the hide-specific-menu option is shown')

    @api.depends_context()
    def _compute_is_show_specific_menu(self):
        for rec in self:
            if rec.has_group('base.group_user'):
                rec.is_show_specific_menu = False
            else:
                for menu in rec.hide_menu_ids:
                    menu.restrict_user_ids = [fields.Command.unlink(rec.id)]
                rec.hide_menu_ids = [fields.Command.clear()]
                rec.is_show_specific_menu = True


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    restrict_user_ids = fields.Many2many(
        'res.users', string="Restricted Users",
        help='Users restricted from accessing this menu.')

    def _filter_visible_menus(self):
        menus = super()._filter_visible_menus()
        if self.env.user.has_group('base.group_system'):
            return menus
        return menus.filtered(lambda m: self.env.user not in m.restrict_user_ids)