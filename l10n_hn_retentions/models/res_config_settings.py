from odoo import _, api, fields, models, tools


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    _legacy_param_suffixes = [
        'apply_retentions',
        'apply_1',
        'apply_12_5',
        'apply_15',
        'account_ret_1',
        'account_ret_12_5',
        'account_ret_15',
        'apply_customer_retentions',
        'apply_customer_1',
        'apply_customer_12_5',
        'apply_customer_15',
        'account_customer_ret_1',
        'account_customer_ret_12_5',
        'account_customer_ret_15',
        'is_exclude_receipt',
    ]

    def _migrate_legacy_params(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for suffix in self._legacy_param_suffixes:
            new_key = f'l10n_hn_retentions.{suffix}'
            legacy_key = f'l10n_hn_gn_retentions.{suffix}'
            new_value = ICP.get_param(new_key)
            if new_value in (None, False, ''):
                legacy_value = ICP.get_param(legacy_key)
                if legacy_value not in (None, False, ''):
                    ICP.set_param(new_key, legacy_value)

    @api.model
    def get_values(self):
        self._migrate_legacy_params()
        return super().get_values()

    # Retenciones de Proveedor
    apply_retentions = fields.Boolean(string='Aplicar retenciones a proveedores', config_parameter='l10n_hn_retentions.apply_retentions')
    apply_1 = fields.Boolean(string='Retención 1% (proveedores)', config_parameter='l10n_hn_retentions.apply_1')
    apply_12_5 = fields.Boolean(string='Retención 12.5% (proveedores)', config_parameter='l10n_hn_retentions.apply_12_5')
    apply_15 = fields.Boolean(string='Retención 15% (proveedores)', config_parameter='l10n_hn_retentions.apply_15')
    account_ret_1  = fields.Many2one(comodel_name='account.account', string='Cuenta para retención 1% (proveedores)', config_parameter='l10n_hn_retentions.account_ret_1')
    account_ret_12_5  = fields.Many2one(comodel_name='account.account', string='Cuenta para retención 12.5% (proveedores)', config_parameter='l10n_hn_retentions.account_ret_12_5')
    account_ret_15 = fields.Many2one(comodel_name='account.account', string='Cuenta para retención 15% (proveedores)', config_parameter='l10n_hn_retentions.account_ret_15')

    # Retenciones de Cliente
    apply_customer_retentions = fields.Boolean(string='Aplicar retenciones a clientes', config_parameter='l10n_hn_retentions.apply_customer_retentions')
    apply_customer_1 = fields.Boolean(string='Retención 1% (clientes)', config_parameter='l10n_hn_retentions.apply_customer_1')
    apply_customer_12_5 = fields.Boolean(string='Retención 12.5% (clientes)', config_parameter='l10n_hn_retentions.apply_customer_12_5')
    apply_customer_15 = fields.Boolean(string='Retención 15% (clientes)', config_parameter='l10n_hn_retentions.apply_customer_15')
    account_customer_ret_1  = fields.Many2one(comodel_name='account.account', string='Cuenta para retención 1% (clientes)', config_parameter='l10n_hn_retentions.account_customer_ret_1')
    account_customer_ret_12_5  = fields.Many2one(comodel_name='account.account', string='Cuenta para retención 12.5% (clientes)', config_parameter='l10n_hn_retentions.account_customer_ret_12_5')
    account_customer_ret_15 = fields.Many2one(comodel_name='account.account', string='Cuenta para retención 15% (clientes)', config_parameter='l10n_hn_retentions.account_customer_ret_15')


    is_exclude_receipt = fields.Boolean(string='')
    
    # def set_values(self):
    #     res = super(ResConfigSettings, self).set_values()
    #     obj_config = self.env['ir.config_parameter']
    #
    #     if self.apply_retentions:
    #         obj_config.set_param('l10n_hn_retentions.apply_retentions', self.apply_retentions)
    #
    #     if self.is_exclude_receipt:
    #         obj_config.set_param('l10n_hn_retentions.is_exclude_receipt', self.is_exclude_receipt)
    #
    #     if self.apply_1:
    #         obj_config.set_param('l10n_hn_retentions.apply_1', self.apply_1)
    #         obj_config.set_param('l10n_hn_retentions.account_ret_1', self.account_ret_1.id)
    #
    #     if self.apply_12_5:
    #         obj_config.set_param('l10n_hn_retentions.apply_12_5', self.apply_12_5)
    #         obj_config.set_param('l10n_hn_retentions.account_ret_12_5', self.account_ret_12_5.id)
    #
    #     if self.apply_15:
    #         obj_config.set_param('l10n_hn_retentions.apply_15', self.apply_15)
    #         obj_config.set_param('l10n_hn_retentions.account_ret_15', self.account_ret_15.id)
    #
    #
    #     # Pagos de clientes
    #     if self.apply_customer_retentions:
    #         obj_config.set_param('l10n_hn_retentions.apply_customer_retentions', self.apply_customer_retentions)
    #
    #     if self.apply_customer_1:
    #         obj_config.set_param('l10n_hn_retentions.apply_customer_1', self.apply_customer_1)
    #         obj_config.set_param('l10n_hn_retentions.account_customer_ret_1', self.account_customer_ret_1.id)
    #
    #     if self.apply_customer_12_5:
    #         obj_config.set_param('l10n_hn_retentions.apply_customer_12_5', self.apply_customer_12_5)
    #         obj_config.set_param('l10n_hn_retentions.account_customer_ret_12_5', self.account_customer_ret_12_5.id)
    #
    #     if self.apply_customer_15:
    #         obj_config.set_param('l10n_hn_retentions.apply_customer_15', self.apply_customer_15)
    #         obj_config.set_param('l10n_hn_retentions.account_customer_ret_15', self.account_customer_ret_15.id)
    #
    #     return res
    #
    # @api.model
    # def get_values(self):
    #     res = super(ResConfigSettings, self).get_values()
    #     ICPSudo = self.env['ir.config_parameter'].sudo()
    #     # print('------------------------------------>', self.env['account.account'].search([('id','=',int(ICPSudo.get_param('l10n_hn_retentions.account_ret_1')))], limit=1).name)
    #     res.update(
    #         # Proveedor
    #         apply_retentions = ICPSudo.get_param('l10n_hn_retentions.apply_retentions'),
    #         is_exclude_receipt = ICPSudo.get_param('l10n_hn_retentions.is_exclude_receipt'),
    #         apply_1 = ICPSudo.get_param('l10n_hn_retentions.apply_1'),
    #         account_ret_1 = self.env['account.account'].search([('id','=',int(ICPSudo.get_param('l10n_hn_retentions.account_ret_1')))], limit=1).id,
    #         apply_12_5 = ICPSudo.get_param('l10n_hn_retentions.apply_12_5'),
    #         account_ret_12_5 = self.env['account.account'].search([('id','=',int(ICPSudo.get_param('l10n_hn_retentions.account_ret_12_5')))], limit=1).id,
    #         apply_15 = ICPSudo.get_param('l10n_hn_retentions.apply_15'),
    #         account_ret_15 = self.env['account.account'].search([('id','=',int(ICPSudo.get_param('l10n_hn_retentions.account_ret_15')))], limit=1).id,
    #
    #         # Cliente
    #         apply_customer_retentions = ICPSudo.get_param('l10n_hn_retentions.apply_customer_retentions'),
    #         apply_customer_1 = ICPSudo.get_param('l10n_hn_retentions.apply_customer_1'),
    #         apply_customer_12_5 = ICPSudo.get_param('l10n_hn_retentions.apply_customer_12_5'),
    #         apply_customer_15 = ICPSudo.get_param('l10n_hn_retentions.apply_customer_15'),
    #         account_customer_ret_1 = self.env['account.account'].search([('id','=',int(ICPSudo.get_param('l10n_hn_retentions.account_customer_ret_1')))], limit=1).id,
    #         account_customer_ret_12_5 = self.env['account.account'].search([('id','=',int(ICPSudo.get_param('l10n_hn_retentions.account_customer_ret_12_5')))], limit=1).id,
    #         account_customer_ret_15 = self.env['account.account'].search([('id','=',int(ICPSudo.get_param('l10n_hn_retentions.account_customer_ret_15')))], limit=1).id,
    #     )
    #
    #     return res