# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ContractBenefitTemplate(models.Model):
    _name = "l10n.hn.contract.benefit.template"
    _description = "Contract Benefit Template"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, help="Unique code used to identify the benefit.")
    sequence = fields.Integer(default=10)
    structure_type_id = fields.Many2one(
        "hr.payroll.structure.type",
        required=True,
        ondelete="cascade",
        string="Salary Structure Type",
    )
    periodicity = fields.Selection(
        [
            ("monthly", "Mensual"),
            ("yearly", "Anual"),
            ("one_time", "Único"),
        ],
        default="monthly",
        required=True,
    )
    default_amount_employee = fields.Monetary(
        string="Monto empleado",
        currency_field="currency_id",
        help="Importe que se reflejará en el recibo del empleado.",
    )
    default_amount_company = fields.Monetary(
        string="Costo empresa",
        currency_field="currency_id",
        help="Costo mensual/anual asumido por la empresa.",
    )
    is_deduction = fields.Boolean(
        string="Es deducción",
        help="Permite restar el monto en lugar de sumarlo al costo total.",
    )
    include_in_payslip = fields.Boolean(
        string="Enviar a nómina",
        help="Si está activo se agrega un input automático en el recibo.",
        default=True,
    )
    input_code = fields.Char(
        string="Código de entrada",
        help="Código de input de nómina que se llenará automáticamente.",
    )
    amount_source = fields.Selection(
        [
            ("employee", "Monto empleado"),
            ("company", "Monto empresa"),
        ],
        default="employee",
        string="Fuente en nómina",
    )
    description = fields.Text()
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Moneda",
        readonly=True,
        store=True,
    )

    _benefit_template_code_unique = models.Constraint(
        'UNIQUE (code, structure_type_id, company_id)',
        'El código del beneficio debe ser único por compañía y tipo de estructura.',
    )

    @api.constrains("include_in_payslip", "input_code", "structure_type_id")
    def _check_input_code_template(self):
        for template in self:
            if template.include_in_payslip and not template.input_code:
                raise ValidationError(_("Debe definir un código de entrada cuando el beneficio se envía a nómina."))
            if template.include_in_payslip and template.input_code and template.structure_type_id:
                # Validar que el código existe en las estructuras del tipo
                self._validate_input_code_in_structure(template.input_code, template.structure_type_id)

    def _validate_input_code_in_structure(self, input_code, structure_type):
        """Valida que el código de input existe en las reglas salariales del tipo de estructura."""
        # Buscar todas las estructuras del tipo
        structures = self.env['hr.payroll.structure'].search([
            ('structure_type_id', '=', structure_type.id)
        ])
        if not structures:
            # Si no hay estructuras del tipo, permitir el código
            return True
        
        # Obtener todas las reglas de todas las estructuras
        all_rules = structures.mapped('rule_ids')
        # Obtener todos los códigos de input de las reglas
        all_input_codes = all_rules.mapped('input_ids.code')
        
        if input_code not in all_input_codes:
            raise ValidationError(_(
                "El código de entrada '%s' no existe en ninguna regla salarial "
                "del tipo de estructura '%s'. Por favor, verifique que el código "
                "esté definido en las reglas salariales."
            ) % (input_code, structure_type.name))


class ContractBenefitLine(models.Model):
    _name = "l10n.hn.contract.benefit.line"
    _description = "Contract Benefit Line"
    _order = "sequence, id"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    version_id = fields.Many2one(
        "hr.version",
        required=True,
        ondelete="cascade",
        string="Contrato",
        index=True,
    )
    template_id = fields.Many2one(
        "l10n.hn.contract.benefit.template",
        ondelete="set null",
        string="Plantilla",
    )
    periodicity = fields.Selection(
        [
            ("monthly", "Mensual"),
            ("yearly", "Anual"),
            ("one_time", "Único"),
        ],
        default="monthly",
        required=True,
    )
    amount_employee = fields.Monetary(
        string="Monto empleado",
        currency_field="currency_id",
    )
    amount_company = fields.Monetary(
        string="Costo empresa",
        currency_field="currency_id",
    )
    is_deduction = fields.Boolean(
        string="Es deducción",
        help="Si está activo se resta en lugar de sumarse al costo.",
    )
    include_in_payslip = fields.Boolean(
        string="Enviar a nómina",
        default=True,
        help="Cuando está activo genera un input automático en la nómina mensual.",
    )
    input_code = fields.Char(
        string="Código de entrada",
        help="Código del input que debe existir en las reglas salariales.",
    )
    amount_source = fields.Selection(
        [
            ("employee", "Monto empleado"),
            ("company", "Monto empresa"),
        ],
        default="employee",
        string="Fuente en nómina",
    )
    notes = fields.Text()
    company_cost_yearly = fields.Monetary(
        compute="_compute_yearly_amounts",
        store=True,
        string="Costo anual empresa",
        currency_field="currency_id",
    )
    employee_amount_yearly = fields.Monetary(
        compute="_compute_yearly_amounts",
        store=True,
        string="Monto anual empleado",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="version_id.company_id.currency_id",
        store=True,
        readonly=True,
    )

    @api.onchange("template_id")
    def _onchange_template_id(self):
        for line in self:
            if line.template_id:
                line.name = line.template_id.name
                line.code = line.template_id.code
                line.periodicity = line.template_id.periodicity
                line.amount_employee = line.template_id.default_amount_employee
                line.amount_company = line.template_id.default_amount_company
                line.is_deduction = line.template_id.is_deduction
                line.include_in_payslip = line.template_id.include_in_payslip
                line.input_code = line.template_id.input_code
                line.amount_source = line.template_id.amount_source

    def _get_yearly_factor(self):
        self.ensure_one()
        if self.periodicity == "monthly":
            return 12.0
        return 1.0

    def _get_signed_amount(self, amount):
        self.ensure_one()
        return -(amount or 0.0) if self.is_deduction else (amount or 0.0)

    @api.depends("amount_company", "amount_employee", "periodicity", "is_deduction")
    def _compute_yearly_amounts(self):
        for line in self:
            factor = line._get_yearly_factor()
            line.company_cost_yearly = line._get_signed_amount(line.amount_company) * factor
            line.employee_amount_yearly = line._get_signed_amount(line.amount_employee) * factor

    def _get_payslip_amount(self):
        self.ensure_one()
        amount = self.amount_company if self.amount_source == "company" else self.amount_employee
        return self._get_signed_amount(amount)

    @api.constrains("include_in_payslip", "input_code", "version_id")
    def _check_input_code_line(self):
        for line in self:
            if line.include_in_payslip and not (line.input_code or line.template_id.input_code):
                raise ValidationError(_("Debe definir un código de entrada en la línea o su plantilla para generar inputs de nómina."))
            # Validar código si existe estructura en el contrato
            if line.include_in_payslip and line.version_id and line.version_id.struct_id:
                input_code = line.input_code or line.template_id.input_code
                if input_code:
                    line._validate_input_code_in_contract_structure(input_code, line.version_id)

    def _validate_input_code_in_contract_structure(self, input_code, version):
        """Valida que el código de input existe en las reglas salariales de la estructura del contrato."""
        struct = version.struct_id
        if not struct:
            return True
        
        # Obtener todas las reglas de la estructura (incluyendo padres)
        all_structures = struct._get_parent_structure() if hasattr(struct, '_get_parent_structure') else struct
        all_rules = all_structures.mapped('rule_ids')
        # Obtener todos los códigos de input de las reglas
        all_input_codes = all_rules.mapped('input_ids.code')
        
        if input_code not in all_input_codes:
            raise ValidationError(_(
                "El código de entrada '%s' no existe en ninguna regla salarial "
                "de la estructura '%s'. Por favor, verifique que el código "
                "esté definido en las reglas salariales o cree el input correspondiente."
            ) % (input_code, struct.name))


