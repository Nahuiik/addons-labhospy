# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class GnFiscalDiscountRule(models.Model):
    _name = 'gn.fiscal.discount.rule'
    _description = 'Matriz de descuento fiscal (tercera/cuarta edad / paciente especial)'
    _order = 'sequence, id'

    _matrix_code_company_uniq = models.Constraint(
        'UNIQUE (matrix_code, company_id)',
        'Solo puede existir una fila por tipo de matriz y compañía.',
    )

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    matrix_code = fields.Selection(
        selection=[
            ('third_age', 'Tercera edad (60 a 79 años cumplidos)'),
            ('fourth_age', 'Cuarta edad (80 años cumplidos o más)'),
            ('special_patient', 'Paciente especial (sin rango de edad; menores de 60 años)'),
        ],
        string='Tipo de matriz',
        required=True,
    )
    age_min = fields.Integer(
        string='Edad mínima (años cumplidos)',
        readonly=True,
        help='Fijado automáticamente según el tipo de matriz.',
    )
    age_max = fields.Integer(
        string='Edad máxima (años cumplidos)',
        readonly=True,
        help='0 = sin límite superior (solo cuarta edad).',
    )
    discount_percent = fields.Float(
        string='Descuento %',
        digits=(16, 2),
        required=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._gn_apply_matrix_ages(vals)
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        code = vals.get('matrix_code', self.matrix_code)
        vals['matrix_code'] = code
        self._gn_apply_matrix_ages(vals)
        return super().write(vals)

    def _gn_apply_matrix_ages(self, vals):
        code = vals.get('matrix_code')
        if not code:
            return
        if code == 'third_age':
            vals['age_min'] = 60
            vals['age_max'] = 79
        elif code == 'fourth_age':
            vals['age_min'] = 80
            vals['age_max'] = 0
        elif code == 'special_patient':
            vals['age_min'] = 0
            vals['age_max'] = 0

    @api.model
    def migrate_matrix_from_xml_ids(self):
        """Actualiza matriz y % desde XML IDs (ej. tras actualizar desde 19.0.1.0.0). Idempotente."""
        mapping = [
            ('gn_discount_fiscal.gn_fiscal_rule_age_60_79', 'third_age', 30.0),
            ('gn_discount_fiscal.gn_fiscal_rule_age_80', 'fourth_age', 40.0),
            ('gn_discount_fiscal.gn_fiscal_rule_special_patient', 'special_patient', 20.0),
        ]
        for xmlid, code, pct in mapping:
            rec = self.env.ref(xmlid, raise_if_not_found=False)
            if not rec:
                continue
            vals = {'matrix_code': code, 'discount_percent': pct}
            vals['matrix_code'] = code
            self._gn_apply_matrix_ages(vals)
            rec.write(vals)

    @api.constrains('matrix_code', 'age_min', 'age_max', 'discount_percent')
    def _check_rule_values(self):
        for rule in self:
            if rule.discount_percent < 0 or rule.discount_percent > 100:
                raise ValidationError(_('El descuento debe estar entre 0 y 100.'))
            if rule.matrix_code == 'third_age':
                if rule.age_min != 60 or rule.age_max != 79:
                    raise ValidationError(
                        _('Tercera edad debe ser de 60 a 79 años cumplidos.')
                    )
            elif rule.matrix_code == 'fourth_age':
                if rule.age_min != 80 or rule.age_max != 0:
                    raise ValidationError(
                        _('Cuarta edad debe ser desde 80 años cumplidos (sin tope superior).')
                    )
            elif rule.matrix_code == 'special_patient':
                if rule.age_min or rule.age_max:
                    raise ValidationError(
                        _('Paciente especial no debe tener rango de edad.')
                    )
