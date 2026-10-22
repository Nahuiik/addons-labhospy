# -*- coding: utf-8 -*-
"""Restaurar jerarquía Contactos → Configuración si quedó huérfana."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE ir_ui_menu AS config
           SET parent_id = contacts.id,
               name = CASE
                   WHEN config.name->>'en_US' = 'contacts.res_partner_menu_config'
                   THEN jsonb_set(config.name, '{en_US}', '"Configuration"'::jsonb)
                   ELSE config.name
               END
          FROM ir_model_data AS config_data,
               ir_model_data AS contacts_data,
               ir_ui_menu AS contacts
         WHERE config_data.module = 'contacts'
           AND config_data.name = 'res_partner_menu_config'
           AND config_data.model = 'ir.ui.menu'
           AND config.id = config_data.res_id
           AND contacts_data.module = 'contacts'
           AND contacts_data.name = 'menu_contacts'
           AND contacts_data.model = 'ir.ui.menu'
           AND contacts.id = contacts_data.res_id
           AND config.parent_id IS DISTINCT FROM contacts.id
        """
    )
