from odoo import models, fields, _, api
from odoo.exceptions import ValidationError, UserError, AccessError

DOMAIN_SEARCH = {
    ("=", False): ("=", 0),
    ("=", True): (">=", 1),
    ("!=", False): (">=", 1),
    ("!=", True): ("=", 0),
}


class res_partner(models.Model):
    _inherit = 'res.partner'

    is_customer = fields.Boolean(
        compute='_compute_is_customer',
        inverse='_inverse_is_customer',
        search='_search_is_customer',
        string='Is a Customer',
        default=lambda self: self._default_is_customer(),
    )
    is_supplier = fields.Boolean(
        compute='_compute_is_supplier',
        inverse='_inverse_is_supplier',
        search='_search_is_supplier',
        string='Is a Supplier',
        default=lambda self: self._default_is_supplier(),
    )

    @api.depends('customer_rank')
    def _compute_is_customer(self):
        for partner in self:
            if not partner.is_customer:
                partner.is_customer = bool(partner.customer_rank)

    @api.depends('supplier_rank')
    def _compute_is_supplier(self):
        for partner in self:
            if not partner.is_supplier:
                partner.is_supplier = bool(partner.supplier_rank)

    def _inverse_is_customer(self):
        self.filtered(lambda p: not p.is_customer).write({'customer_rank': 0})
        self.filtered(lambda p: p.is_customer and not p.customer_rank).write({'customer_rank': 1})

    def _search_is_customer(self, operator, value):
        if operator not in ['=', '!='] or not isinstance(value, bool):
            raise UserError(_('Operation not supported'))
        operator, value = DOMAIN_SEARCH.get((operator, value))
        return [('customer_rank', operator, value)]

    def _inverse_is_supplier(self):
        self.filtered(lambda p: not p.is_supplier).write({'supplier_rank': 0})
        self.filtered(lambda p: p.is_supplier and not p.supplier_rank).write({'supplier_rank': 1})

    def _search_is_supplier(self, operator, value):
        if operator not in ['=', '!='] or not isinstance(value, bool):
            raise UserError(_('Operation not supported'))
        operator, value = DOMAIN_SEARCH.get((operator, value))
        return [('supplier_rank', operator, value)]

    @api.model
    def _default_is_customer(self):
        return self.env.context.get('res_partner_search_mode') == 'customer'

    @api.model
    def _default_is_supplier(self):
        return self.env.context.get('res_partner_search_mode') == 'supplier'

    def _sync_manual_rank_vals(self, vals):
        """Mantener alineados los flags legacy customer/supplier con is_customer/is_supplier."""
        if 'customer' in vals and 'is_customer' not in vals:
            vals['is_customer'] = bool(vals['customer'])
        if 'supplier' in vals and 'is_supplier' not in vals:
            vals['is_supplier'] = bool(vals['supplier'])
        if 'is_customer' in vals and 'customer' not in vals:
            vals['customer'] = bool(vals['is_customer'])
        if 'is_supplier' in vals and 'supplier' not in vals:
            vals['supplier'] = bool(vals['is_supplier'])
        return vals

    rtn = fields.Char('RTN', translate=True, size=14, copy=False)
    zip_id = fields.Many2one('res.city.zip', 'ZIP Location')
    exclude_rtn = fields.Boolean(string="Exclude rtn")
    is_branch = fields.Boolean(string='Es Sucursal?')

    # Nuevo contraint mas flexible
    @api.constrains('rtn')
    def _check_rtn(self):
        for rec in self:
            if not rec.rtn or rec.exclude_rtn:
                continue
            if self.env['res.partner'].search_count([
                ('rtn', '=', rec.rtn),
                ('id', '!=', rec.id),
            ]) > 0 and not rec.is_branch:
                raise ValidationError(_('RTN debe ser único, a menos que sea una sucursal.'))

    cai_shot = fields.Char("CAI")
    cai_expires_shot = fields.Date("Fecha de Expiración")
    min_number_shot = fields.Char("Número Minimo")
    max_number_shot = fields.Char("Número Maximo")
    customer = fields.Boolean(string="Customer")
    supplier = fields.Boolean(string="Supplier")
    client_code = fields.Char(string='Client Code')
    multiple_cais = fields.Boolean('Aceptar Multiples CAI',default=False)
    supplier_cai_ids = fields.One2many(comodel_name='supplier.cai', inverse_name='contact_id',copy=False)
    
    def _context_wants_customer(self):
        ctx = self.env.context
        return bool(
            ctx.get('default_customer')
            or ctx.get('default_customer_rank')
            or ctx.get('search_default_customer')
            or ctx.get('res_partner_search_mode') == 'customer'
        )

    def _context_wants_supplier(self):
        ctx = self.env.context
        return bool(
            ctx.get('default_supplier')
            or ctx.get('default_supplier_rank')
            or ctx.get('search_default_supplier')
            or ctx.get('res_partner_search_mode') == 'supplier'
        )

    def _update_vals_with_vat(self, vals, partner=None):
        if 'vat' in vals:
            return vals
        updated_vals = vals.copy()
        exclude = updated_vals['exclude_rtn'] if 'exclude_rtn' in updated_vals else (partner.exclude_rtn if partner else False)
        rtn = updated_vals['rtn'] if 'rtn' in updated_vals else (partner.rtn if partner else False)
        if exclude:
            updated_vals['vat'] = False
        elif 'rtn' in updated_vals or partner:
            updated_vals['vat'] = rtn or False
        return updated_vals

    @api.model_create_multi
    def create(self, vals_list):
        sanitized_vals_list = []
        for vals in vals_list:
            vals_copy = vals.copy()
            if 'rtn' in vals_copy or 'exclude_rtn' in vals_copy:
                vals_copy = self._update_vals_with_vat(vals_copy)
            if 'customer' not in vals_copy and (vals_copy.get('customer_rank', 0) > 0 or self._context_wants_customer()):
                vals_copy['customer'] = True
                vals_copy['is_customer'] = True
            if 'supplier' not in vals_copy and (vals_copy.get('supplier_rank', 0) > 0 or self._context_wants_supplier()):
                vals_copy['supplier'] = True
                vals_copy['is_supplier'] = True
            vals_copy = self._sync_manual_rank_vals(vals_copy)
            sanitized_vals_list.append(vals_copy)
        partners = super().create(sanitized_vals_list)
        if not self.env.context.get('bypass'):
            for partner in partners:
                if partner.is_customer and not partner.client_code:
                    partner.with_context(bypass=True).client_code = self.env['ir.sequence'].next_by_code('customer.sequence') or ''
        return partners

    def write(self, vals):
        vals = self._sync_manual_rank_vals(dict(vals))
        if 'rtn' in vals or 'exclude_rtn' in vals:
            res = True
            for partner in self:
                partner_vals = self._update_vals_with_vat(vals, partner)
                res = res and super(res_partner, partner).write(partner_vals)
        else:
            res = super(res_partner, self).write(vals)
        # Lógica específica de Honduras: generar client_code para clientes
        if not self.env.context.get('bypass'):
            for rec in self:
                if rec.is_customer and not rec.client_code:
                    rec.with_context(bypass=True).client_code = self.env['ir.sequence'].next_by_code('customer.sequence') or ''
        return res

    @api.onchange('customer')
    def _onchange_customer_manual_rank(self):
        self.is_customer = bool(self.customer)

    @api.onchange('supplier')
    def _onchange_supplier_manual_rank(self):
        self.is_supplier = bool(self.supplier)

    @api.onchange('rtn')
    def _onchange_rtn_digits_only(self):
        if not self.rtn:
            self.vat = False
            return
        digits_only = ''.join(ch for ch in self.rtn if ch.isdigit())
        if digits_only != self.rtn:
            self.rtn = digits_only
            warning = {
                'warning': {
                    'title': _('RTN inválido'),
                    'message': _('Este campo solo acepta números.'),
                }
            }
        else:
            warning = None
        if self.exclude_rtn:
            self.vat = False
        else:
            self.vat = self.rtn
        if warning:
            return warning

    @api.onchange('exclude_rtn')
    def _onchange_exclude_rtn(self):
        if self.exclude_rtn:
            self.vat = False
        else:
            self.vat = self.rtn


    @api.constrains('rtn', 'exclude_rtn')
    def validate_rtn(self):
        for partner in self:
            if partner.exclude_rtn or not partner.rtn:
                continue
            if not partner.rtn.isdigit():
                raise ValidationError(_('El RTN solo debe contener números.'))
            if len(partner.rtn) != 14:
                raise ValidationError(_('El tamaño del RTN debe ser igual a 14 caracteres.'))
            
    @api.onchange('city_id')
    def _onchange_city_id(self):
        if not self.zip_id:
            super()._onchange_city_id()
        if self.zip_id and self.city_id != self.zip_id.city_id:
            self.update({
                'zip_id': False,
                'zip': False,
                'city': False,
            })
        if self.city_id and self.country_enforce_cities:
            return {
                'domain': {
                    'zip_id': [('city_id', '=', self.city_id.id)]
                },
            }
        return {'domain': {'zip_id': []}}

    @api.onchange('country_id')
    def _onchange_country_id(self):
        res = super()._onchange_country_id()
        if self.zip_id and self.zip_id.city_id.country_id != self.country_id:
            self.zip_id = False
        return res

    @api.onchange('zip_id')
    def _onchange_zip_id(self):
        if self.zip_id:
            vals = {
                'city_id': self.zip_id.city_id,
                'zip': self.zip_id.name,
                'city': self.zip_id.city_id.name,
            }
            if self.zip_id.city_id.country_id:
                vals.update({'country_id': self.zip_id.city_id.country_id})
            if self.zip_id.city_id.state_id:
                vals.update({'state_id': self.zip_id.city_id.state_id})
            self.update(vals)
        elif not self.country_enforce_cities:
            self.city_id = False

    @api.constrains('zip_id', 'country_id', 'city_id', 'state_id')
    def _check_zip(self):
        if self.env.context.get('skip_check_zip'):
            return
        for rec in self:
            if not rec.zip_id:
                continue
            if rec.zip_id.city_id.state_id != rec.state_id:
                raise ValidationError(_(
                    "The state of the partner %s differs from that in "
                    "location %s") % (rec.name, rec.zip_id.name))
            if rec.zip_id.city_id.country_id != rec.country_id:
                raise ValidationError(_(
                    "The country of the partner %s differs from that in "
                    "location %s") % (rec.name, rec.zip_id.name))
            if rec.zip_id.city_id != rec.city_id:
                raise ValidationError(_(
                    "The city of partner %s differs from that in "
                    "location %s") % (rec.name, rec.zip_id.name))

    @api.onchange('state_id')
    def _onchange_state_id(self):
        vals = {}
        if self.state_id.country_id:
            vals.update({'country_id': self.state_id.country_id})
        if self.zip_id and self.state_id != self.zip_id.city_id.state_id:
            vals.update({
                'zip_id': False,
                'zip': False,
                'city': False,
            })
        self.update(vals)
