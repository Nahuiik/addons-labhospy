# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrVersion(models.Model):
    _inherit = "hr.version"

    benefit_line_ids = fields.One2many(
        "l10n.hn.contract.benefit.line",
        "version_id",
        string="Beneficios salariales",
        copy=True,
    )
    holidays = fields.Float(
        string="Días adicionales",
        help="Número de días de vacaciones adicionales reconocidos por el contrato.",
        groups="hr.group_hr_manager",
    )
    wage_with_holidays = fields.Monetary(
        string="Salario con vacaciones",
        compute="_compute_wage_with_holidays",
        inverse="_inverse_wage_with_holidays",
        store=True,
        tracking=True,
        groups="hr.group_hr_manager",
    )
    wage_on_signature = fields.Monetary(
        string="Salario al firmar",
        tracking=True,
        groups="hr.group_hr_manager",
        help="Monto que se mostrará en el documento de firma del contrato.",
    )
    final_yearly_costs = fields.Monetary(
        string="Costo anual empresa",
        compute="_compute_final_yearly_costs",
        store=True,
        tracking=True,
        groups="hr.group_hr_manager",
    )
    monthly_yearly_costs = fields.Monetary(
        string="Costo mensual empresa",
        compute="_compute_monthly_yearly_costs",
        store=True,
        groups="hr.group_hr_manager",
    )
    leave_allocation_id = fields.Many2one(
        "hr.leave.allocation",
        string="Asignación de vacaciones",
        readonly=True,
        groups="hr.group_hr_user",
    )

    def _is_salary_sacrifice(self):
        self.ensure_one()
        return bool(self.holidays)

    def _get_yearly_cost_sacrifice_ratio(self):
        self.ensure_one()
        base_days = self.company_id.hr_contract_work_days_per_year or 0.0
        if not base_days:
            return 1.0
        return max(0.01, 1.0 - (self.holidays or 0.0) / base_days)

    def _get_benefits_costs(self):
        self.ensure_one()
        return sum(self.benefit_line_ids.mapped("company_cost_yearly"))

    def _get_salary_costs_factor(self):
        """
        Calculate the factor to convert wage to yearly cost based on schedule_pay.
        Returns the number of pay periods per year.
        """
        self.ensure_one()
        schedule_pay_factors = {
            'monthly': 12.0,
            'quarterly': 4.0,
            'semi-annually': 2.0,
            'annually': 1.0,
            'weekly': 52.0,
            'bi-weekly': 26.0,
            'bi-monthly': 6.0,
        }
        return schedule_pay_factors.get(self.schedule_pay or 'monthly', 12.0)

    def _get_yearly_cost_from_wage(self):
        self.ensure_one()
        return self._get_benefits_costs() + self._get_salary_costs_factor() * (self.wage or 0.0)

    def _get_yearly_cost_from_wage_with_holidays(self, wage_with_holidays=None):
        self.ensure_one()
        ratio = self._get_yearly_cost_sacrifice_ratio()
        wage_value = wage_with_holidays if wage_with_holidays is not None else self.wage_with_holidays
        return (self._get_benefits_costs() + self._get_salary_costs_factor() * (wage_value or 0.0)) / ratio

    @api.depends(
        "benefit_line_ids.company_cost_yearly",
        "wage",
        "wage_with_holidays",
        "holidays",
    )
    def _compute_final_yearly_costs(self):
        for version in self:
            if version._is_salary_sacrifice():
                version.final_yearly_costs = version._get_yearly_cost_from_wage_with_holidays()
            else:
                version.final_yearly_costs = version._get_yearly_cost_from_wage()

    @api.depends("final_yearly_costs")
    def _compute_monthly_yearly_costs(self):
        for version in self:
            version.monthly_yearly_costs = (version.final_yearly_costs or 0.0) / 12.0

    @api.depends("holidays", "wage", "benefit_line_ids.company_cost_yearly")
    def _compute_wage_with_holidays(self):
        for version in self:
            if version._is_salary_sacrifice():
                yearly = version._get_yearly_cost_from_wage()
                ratio = version._get_yearly_cost_sacrifice_ratio()
                benefits = version._get_benefits_costs()
                salary_factor = version._get_salary_costs_factor() or 1.0
                version.wage_with_holidays = (yearly * ratio - benefits) / salary_factor
            else:
                version.wage_with_holidays = version.wage
            if not version.wage_on_signature:
                version.wage_on_signature = version.wage_with_holidays

    def _inverse_wage_with_holidays(self):
        for version in self:
            if version._is_salary_sacrifice():
                yearly = version._get_yearly_cost_from_wage_with_holidays(version.wage_with_holidays)
                salary_factor = version._get_salary_costs_factor() or 1.0
                benefits = version._get_benefits_costs()
                version.wage = (yearly - benefits) / salary_factor
            else:
                version.wage = version.wage_with_holidays

    def _get_structure_type_id(self):
        """Get structure_type_id from struct_id if structure_type_id doesn't exist directly."""
        self.ensure_one()
        # Check if structure_type_id exists directly on hr.version
        if hasattr(self, 'structure_type_id') and self.structure_type_id:
            return self.structure_type_id
        # Fallback to struct_id.structure_type_id if it exists
        if self.struct_id and hasattr(self.struct_id, 'structure_type_id') and self.struct_id.structure_type_id:
            return self.struct_id.structure_type_id
        # Return empty recordset if not found
        return self.env['hr.payroll.structure.type'].browse()

    @api.onchange("struct_id")
    def _onchange_struct_id(self):
        self._load_benefit_templates()

    def _prepare_benefit_line_vals(self, template):
        self.ensure_one()
        return {
            "template_id": template.id,
            "name": template.name,
            "code": template.code,
            "periodicity": template.periodicity,
            "amount_employee": template.default_amount_employee,
            "amount_company": template.default_amount_company,
            "is_deduction": template.is_deduction,
            "include_in_payslip": template.include_in_payslip,
            "input_code": template.input_code,
            "amount_source": template.amount_source,
        }

    def _load_benefit_templates(self):
        BenefitTemplate = self.env["l10n.hn.contract.benefit.template"]
        for version in self:
            structure_type = version._get_structure_type_id()
            if not structure_type or not version.company_id:
                continue
            templates = BenefitTemplate.search(
                [
                    ("structure_type_id", "=", structure_type.id if hasattr(structure_type, 'id') else structure_type),
                    ("company_id", "in", [version.company_id.id, False]),
                ]
            )
            if not templates:
                continue
            existing_templates = version.benefit_line_ids.mapped("template_id")
            commands = []
            for template in templates:
                if template in existing_templates:
                    continue
                commands.append((0, 0, version._prepare_benefit_line_vals(template)))
            if commands:
                version.benefit_line_ids = commands

    def action_generate_timeoff_allocation(self):
        self.ensure_one()
        if not self.employee_id:
            raise UserError(_("Solo los contratos asignados a un empleado pueden generar vacaciones."))
        if not self.holidays:
            raise UserError(_("Defina los días adicionales antes de crear la asignación."))
        company = self.company_id
        if not company.hr_contract_timeoff_auto_allocation_type_id:
            raise UserError(_("Configure el tipo de ausencia por defecto en Ajustes › Recursos Humanos."))
        LeaveAllocation = self.env["hr.leave.allocation"].sudo()
        allocation = LeaveAllocation.create({
            "name": _("Asignación automática desde contrato"),
            "employee_id": self.employee_id.id,
            "holiday_status_id": company.hr_contract_timeoff_auto_allocation_type_id.id,
            "number_of_days": self.holidays,
            "notes": _("Creado automáticamente desde el contrato de %s.") % self.employee_id.name,
            "state": "validate",
        })
        self.leave_allocation_id = allocation.id
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.leave.allocation",
            "view_mode": "form",
            "res_id": allocation.id,
        }

    def action_view_leave_allocation(self):
        self.ensure_one()
        if not self.leave_allocation_id:
            raise UserError(_("Aún no se ha generado una asignación para este contrato."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.leave.allocation",
            "view_mode": "form",
            "res_id": self.leave_allocation_id.id,
        }

    def get_attribute(self, code, attribute):
        """
        Get an attribute value from an advantage template by code.
        Compatible with Odoo 18 Enterprise hr_contract_salary module.
        """
        advantage_template = self.env['hr.version.advantage.template'].search([('code', '=', code)], limit=1)
        if not advantage_template:
            return None
        return getattr(advantage_template, attribute, None)

    def set_attribute_value(self, code, active):
        """
        Set or unset an attribute value from an advantage template by code.
        Compatible with Odoo 18 Enterprise hr_contract_salary module.
        
        :param code: Code of the advantage template
        :param active: If True, sets the default value, if False, sets to 0.0
        """
        for contract in self:
            advantage_template = self.env['hr.version.advantage.template'].search([('code', '=', code)], limit=1)
            
            # If the code matches a benefit template, we handle it differently
            benefit_template = self.env['l10n.hn.contract.benefit.template'].search([('code', '=', code)], limit=1)
            if benefit_template:
                # Find or create the benefit line
                benefit_line = contract.benefit_line_ids.filtered(lambda b: b.code == code or b.template_id == benefit_template)
                if active:
                    if not benefit_line:
                        # Create new benefit line from template
                        contract.benefit_line_ids = [(0, 0, contract._prepare_benefit_line_vals(benefit_template))]
                    else:
                        # Update existing with template values
                        benefit_line.write(contract._prepare_benefit_line_vals(benefit_template))
                else:
                    # Remove or set amount to 0
                    if benefit_line:
                        benefit_line.amount_employee = 0.0
                        benefit_line.amount_company = 0.0
                continue
            
            # For standard advantage templates, use default behavior if field exists
            if advantage_template and hasattr(contract, code):
                if active:
                    setattr(contract, code, advantage_template.default_value)
                else:
                    setattr(contract, code, 0.0)

    def action_open_apply_template_wizard(self):
        """Abrir wizard para aplicar plantilla de beneficios."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Aplicar Plantilla de Beneficios"),
            "res_model": "l10n.hn.contract.template.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_contract_id": self.id,
            },
        }



