# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # False por defecto: si fuera True, todo contacto persona quedaría sujeto a DNI y fecha
    # de nacimiento obligatorios sin haber marcado «Es Paciente» (bloqueos al guardar).
    gn_is_patient = fields.Boolean(
        string='Es Paciente',
        default=False,
        copy=False,
    )
    gn_dni = fields.Char(
        string='DNI',
        size=13,
        copy=False,
        help='Solo números, máximo 13 dígitos. Obligatorio para pacientes.',
    )
    gn_is_special_patient = fields.Boolean(string='Paciente Especial')
    gn_birthdate = fields.Date(string='Fecha de nacimiento')
    gn_age_years = fields.Integer(
        string='Años',
        compute='_compute_gn_age_parts',
    )
    gn_age_months = fields.Integer(
        string='Meses',
        compute='_compute_gn_age_parts',
    )
    gn_age_days = fields.Integer(
        string='Días',
        compute='_compute_gn_age_parts',
    )
    gn_age_display = fields.Char(
        string='Edad',
        compute='_compute_gn_age_parts',
    )
    gn_fiscal_discount_percent = fields.Float(
        string='Descuento fiscal aplicable %',
        digits=(16, 2),
        compute='_compute_gn_fiscal_discount_percent',
        help='Solo contactos tipo Persona. Prioridad: 80+ (4.ª edad) > 60–79 (3.ª edad) > paciente especial (menores de 60 o sin fecha).',
    )
    gn_fiscal_ribbon_type = fields.Selection(
        selection=[
            ('fourth', 'Cuarta edad'),
            ('third', 'Tercera edad'),
            ('special', 'Paciente especial'),
        ],
        string='Cintillo fiscal',
        compute='_compute_gn_fiscal_ribbon_type',
    )

    @api.depends('gn_birthdate')
    def _compute_gn_age_parts(self):
        today = fields.Date.context_today(self)
        for partner in self:
            if not partner.gn_birthdate:
                partner.gn_age_years = 0
                partner.gn_age_months = 0
                partner.gn_age_days = 0
                partner.gn_age_display = ''
                continue
            delta = relativedelta(today, partner.gn_birthdate)
            partner.gn_age_years = delta.years
            partner.gn_age_months = delta.months
            partner.gn_age_days = delta.days
            partner.gn_age_display = _(
                '%(years)s años %(months)s meses %(days)s días'
            ) % {
                'years': delta.years,
                'months': delta.months,
                'days': delta.days,
            }

    @api.depends('gn_birthdate', 'gn_is_special_patient', 'company_id', 'is_company')
    def _compute_gn_fiscal_discount_percent(self):
        for partner in self:
            partner.gn_fiscal_discount_percent = partner._gn_get_fiscal_discount_percent()

    @api.depends('gn_birthdate', 'gn_is_special_patient', 'is_company')
    def _compute_gn_fiscal_ribbon_type(self):
        for partner in self:
            partner.gn_fiscal_ribbon_type = partner._gn_fiscal_tier()

    def _gn_fiscal_tier(self):
        """4.ª edad > 3.ª edad > paciente especial (misma prioridad que el descuento). Solo personas."""
        self.ensure_one()
        if self.is_company:
            return False
        age = self._gn_completed_age_years()
        if age is not None:
            if age >= 80:
                return 'fourth'
            if age >= 60:
                return 'third'
        if self.gn_is_special_patient:
            return 'special'
        return False

    def _gn_completed_age_years(self):
        """Años cumplidos a la fecha de hoy."""
        self.ensure_one()
        if not self.gn_birthdate:
            return None
        today = fields.Date.context_today(self)
        return relativedelta(today, self.gn_birthdate).years

    def _gn_has_fiscal_rtn(self):
        """
        Indica si el contacto tiene RTN para facturación (l10n_hn_account: `rtn` / `exclude_rtn`;
        `vat` se sincroniza con RTN en la localización).
        """
        self.ensure_one()
        if self.exclude_rtn:
            return False
        return bool((self.rtn or '').strip())

    def _gn_fiscal_rule_percent(self, matrix_code):
        self.ensure_one()
        company = self.company_id or self.env.company
        rule = self.env['gn.fiscal.discount.rule'].sudo().search(
            [
                ('company_id', '=', company.id),
                ('matrix_code', '=', matrix_code),
                ('active', '=', True),
            ],
            limit=1,
        )
        return rule.discount_percent if rule else 0.0

    def _gn_get_fiscal_discount_percent(self):
        """
        Prioridad:
        1) 80 años cumplidos o más → cuarta edad (matriz fourth_age).
        2) 60 a 79 años cumplidos → tercera edad (matriz third_age).
        3) Paciente especial sin (1) ni (2): &lt; 60 o sin fecha de nacimiento → special_patient.
        """
        self.ensure_one()
        tier = self._gn_fiscal_tier()
        if tier == 'fourth':
            return self._gn_fiscal_rule_percent('fourth_age')
        if tier == 'third':
            return self._gn_fiscal_rule_percent('third_age')
        if tier == 'special':
            return self._gn_fiscal_rule_percent('special_patient')
        return 0.0

    @api.constrains('gn_is_patient', 'gn_birthdate', 'is_company')
    def _check_gn_birthdate_if_patient(self):
        for partner in self:
            if partner.is_company:
                continue
            if partner.gn_is_patient and not partner.gn_birthdate:
                raise ValidationError(
                    _('Si «Es Paciente» está activo, la fecha de nacimiento es obligatoria.')
                )

    @api.constrains('gn_dni', 'gn_is_patient', 'is_company')
    def _check_gn_dni(self):
        for partner in self:
            if partner.is_company or not partner.gn_is_patient:
                continue
            if not partner.gn_dni:
                raise ValidationError(_('El DNI es obligatorio para pacientes.'))
            if not partner.gn_dni.isdigit():
                raise ValidationError(_('El DNI solo debe contener números.'))
            if not 1 <= len(partner.gn_dni) <= 13:
                raise ValidationError(
                    _('El DNI debe tener entre 1 y 13 dígitos.')
                )

    @api.model
    def _gn_sanitize_dni_val(self, value):
        """Solo dígitos, máximo 13 (mismo criterio que el onchange del RTN en l10n_hn_account)."""
        if value in (False, None, ''):
            return False
        return ''.join(ch for ch in str(value) if ch.isdigit())[:13] or False

    @api.onchange('gn_dni')
    def _onchange_gn_dni_digits(self):
        if not self.gn_dni:
            return
        digits_only = ''.join(ch for ch in self.gn_dni if ch.isdigit())[:13]
        if digits_only != self.gn_dni:
            self.gn_dni = digits_only or False
            return {
                'warning': {
                    'title': _('DNI inválido'),
                    'message': _('Solo se permiten números; máximo 13 dígitos.'),
                }
            }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_company'):
                vals['gn_is_patient'] = False
            if 'gn_dni' in vals:
                vals['gn_dni'] = self._gn_sanitize_dni_val(vals.get('gn_dni'))
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('is_company'):
            vals = dict(vals)
            vals['gn_is_patient'] = False
        if 'gn_dni' in vals:
            vals = dict(vals)
            vals['gn_dni'] = self._gn_sanitize_dni_val(vals.get('gn_dni'))
        res = super().write(vals)
        if self.env.context.get('skip_gn_patient_company_fix'):
            return res
        companies_wrong = self.filtered(lambda p: p.is_company and p.gn_is_patient)
        if companies_wrong:
            super(ResPartner, companies_wrong.with_context(skip_gn_patient_company_fix=True)).write(
                {'gn_is_patient': False}
            )
        return res

    @api.onchange('is_company')
    def _onchange_is_company_gn_patient(self):
        if self.is_company:
            self.gn_is_patient = False

    @api.model
    def _gn_data_ensure_consumidor_final(self):
        """Crea o enlaza el xmlid al contacto CONSUMIDOR FINAL (RTN genérico HN)."""
        generic = '99999999999999'
        Data = self.env['ir.model.data'].sudo()
        if Data.search(
            [
                ('module', '=', 'gn_discount_fiscal'),
                ('name', '=', 'partner_consumidor_final'),
            ]
        ):
            return
        Partner = self.env['res.partner'].sudo()
        partner = Partner.search([('rtn', '=', generic)], limit=1)
        if not partner:
            partner = Partner.create(
                {
                    'name': 'CONSUMIDOR FINAL',
                    'is_company': False,
                    'rtn': generic,
                    'gn_is_patient': False,
                }
            )
        Data.create(
            {
                'name': 'partner_consumidor_final',
                'module': 'gn_discount_fiscal',
                'model': 'res.partner',
                'res_id': partner.id,
                'noupdate': True,
            }
        )

    @api.model
    def _gn_migrate_patients_dni_placeholder(self):
        """Un dígito válido para datos antiguos; sustituir por el DNI real en el contacto."""
        partners = self.search(
            [
                ('gn_is_patient', '=', True),
                ('is_company', '=', False),
                '|',
                ('gn_dni', '=', False),
                ('gn_dni', '=', ''),
            ]
        )
        if partners:
            partners.write({'gn_dni': '0'})
